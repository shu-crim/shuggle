import os
import random
import numpy as np
import cv2
import json
import sklearn.metrics
import matplotlib.pyplot as plt
import matplotlib

def recognition(input_data:list, train_data:list, label_train:list, goal:float) -> list:
    # input_dataの登録順序(input_dataのindexを登録順に並べたもの)
    registration_order = [i for i in range(len(input_data))]
    
    # ここに処理を書く
    random.shuffle(registration_order) #登録順を単にシャッフル

    # 処理結果の画像を返す
    return registration_order


FILEPATH_INPUT_DATA_JSON = r"train/dataset.json"
ANSWER_VALUE_TYPE = "ActiveLearing"
MULTI_DATA = False
INPUT_DATA_TYPE = "vector"

def read_dataset(path_json, answer_value_type=int, multi_data=False, input_data_type="image-3ch"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_open = open(os.path.join(base_dir, path_json), 'r')
    dataset = json.load(json_open)

    filename_list = []
    input_data_list = [] #入力データ
    correct_list = [] #正解値
    parameter_list = [] #パラメータ
    num_problem = 0

    for item in dataset["data"]:
        try:
            # 正解値
            if type(answer_value_type) is str:
                if answer_value_type == "ActiveLearing":
                    # テストデータのラベルList
                    correct_list.append(item["gt"])
                else:
                    raise(ValueError(f"answer_value_typeの指定({answer_value_type})が不正です。"))
            else:
                raise(ValueError(f"answer_value_typeの指定({answer_value_type})が不正です。"))

            # 入力データ
            data = []
            filename = []
            if input_data_type == "vector":
                # ベクトルList読み込み
                data = np.array(item["vector"], np.float32)
                if "path" in item:
                    filename = item["path"]
                else:
                    filename = ["" for i in range(len(data))]
            else:
                raise(ValueError(f"input_data_typeの指定({input_data_type})が不正です。"))

            # 複数データの場合にひとまとめの行列にする
            if multi_data:
                input_data_list.append(np.array(data, dtype=data[0].dtype))
            else:
                input_data_list.append(data)

            # ファイル名を追加
            filename_list.append(filename)

            # Active learing Taskの場合、学習データをパラメータとして読み込む
            if answer_value_type == "ActiveLearing":
                parameter = [[], [], 0] #[入力データのリスト, ラベルのリスト, P/R目標値]
                if input_data_type == "vector":
                    # ベクトル読み込み
                    parameter[0] = np.array(item["train"], np.float32)
                else:
                    raise(ValueError(f"answer_value_typeの指定({answer_value_type})が不正です。"))
                
                # ラベルと目標値の読み込み
                parameter[1] += item["train-gt"]
                parameter[2] = item["goal"]

                # データ追加
                parameter_list.append(parameter)

            num_problem += 1
        except Exception as e:
            print(f"入力データ({num_problem})の読み込みに失敗しました：{e}")
            continue

    return num_problem, filename_list, input_data_list, parameter_list, correct_list


def caclActiveLearingAccuracy(label_gt, label_estimation, num_class):
    precision = sklearn.metrics.precision_score(label_gt, label_estimation, average=None, labels=[i for i in range(num_class)], zero_division=1)
    recall = sklearn.metrics.recall_score(label_gt, label_estimation, average=None, labels=[i for i in range(num_class)], zero_division=1)

    return precision, recall


def evaluateActiveLearing(num_class:int, train_data:list, label_train:list, valid_data:list, label_valid:list, registration_order:list, goal:float) -> float:
    num_registration_per_valid = 5 #5データずつ登録して評価
    num_valid_data = len(registration_order)
    train_data = np.array(train_data)
    valid_data = np.array(valid_data)
    label_train = np.array(label_train)
    label_valid = np.array(label_valid)
    K = 1
    detail = [] #0%～最大100%登録時点での各クラスのP/R
    registration_rate = -1

    # 評価と登録のループ
    for iValidObject in range(num_valid_data + 1):
        if iValidObject % num_registration_per_valid == 0 or iValidObject == num_valid_data:
            if len(label_train) > 0:
                # Trainデータの登録
                knn = cv2.ml.KNearest_create()
                knn.train(train_data, cv2.ml.ROW_SAMPLE, label_train)

                # Validデータの識別
                ret, results, neighbours, dist = knn.findNearest(valid_data, K)
                label_estimation = results.reshape(label_valid.shape[0]).astype(int)
            else:
                # Validデータの識別結果はすべてclass0
                label_estimation = np.zeros((label_valid.shape[0]), int)

            precision, recall = caclActiveLearingAccuracy(label_valid, label_estimation, num_class)
            
            # 詳細記録
            if iValidObject == 0:
                detail.append([precision, recall])
            else:
                registration_rate_percent = int((iValidObject / num_valid_data) * 100)
                while len(detail) < registration_rate_percent + 1:
                    detail.append(detail[-1]) #最後に登録された結果をコピーする
                detail[registration_rate_percent] = [precision, recall]

            if min(precision) >= goal and min(recall) >= goal and registration_rate < 0:
                print(f"P/R Goal have been achieved! {iValidObject} / {num_valid_data}")
                registration_rate = iValidObject / num_valid_data

        # trainデータの追加
        if iValidObject < num_valid_data:
            # リストから順に選択
            addition_index = registration_order[iValidObject]

            # Trainデータに追加
            additional_data = valid_data[addition_index]
            train_data = np.concatenate([train_data, [additional_data]])
            label_train = np.concatenate([label_train, [label_valid[addition_index]]])

    return registration_rate, detail


def main():
    # データ読み込み
    num_problem, filename_list, input_data_list, parameter_list, correct_list = read_dataset(
        FILEPATH_INPUT_DATA_JSON, ANSWER_VALUE_TYPE, MULTI_DATA, INPUT_DATA_TYPE)

    # ユーザ作成の処理にかける
    answer_list = []
    for i in range(num_problem):
        print(f"Resolve {i+1} / {num_problem}")
        if len(parameter_list[i]) == 0:
            answer_list.append(recognition(input_data_list[i]))
        elif len(parameter_list[i]) == 1:
            answer_list.append(recognition(input_data_list[i], parameter_list[i][0]))
        elif len(parameter_list[i]) == 2:
            answer_list.append(recognition(input_data_list[i], parameter_list[i][0], parameter_list[i][1]))
        elif len(parameter_list[i]) == 3:
            answer_list.append(recognition(input_data_list[i], parameter_list[i][0], parameter_list[i][1], parameter_list[i][2]))

    # 評価
    registration_rate = []
    details = []
    for i in range(num_problem):
        print(f"Evaluate {i+1} / {num_problem}")
        train_data, label_train, goal = parameter_list[i]
        num_class = max(label_train) + 1
        result, detail = evaluateActiveLearing(num_class, train_data, label_train, input_data_list[i], correct_list[i], answer_list[i], goal)
        registration_rate.append(result)
        if len(detail) > 0:
            details.append(detail)
    print(f"Mean Registration Rate: {np.average(np.array(registration_rate))}")

    # 詳細データが存在する場合は登録率[0..100]に対する平均P/Rを算出してグラフ化
    if len(details) > 0:
        details = np.array(details)
        mean_pr = np.average(details, axis=0)
        
        # グラフの描画
        class_name = {
            0: "class0",
            1: "class1",
            2: "class2",
        }

        cmap = matplotlib.colormaps.get_cmap('tab20')
        fig, axs = plt.subplots(1, 2, figsize=(15, 6))

        for i in range(mean_pr.shape[2]):
            axs[0].plot(mean_pr[:, 0, i], label=f'{class_name[i] if i in class_name else f"{i}"}', color=cmap(i))
        axs[0].set_title('Precision')
        axs[0].set_xlabel('Registration Rate [%]')
        axs[0].set_ylabel('Precision')
        axs[0].legend()

        for i in range(mean_pr.shape[2]):
            axs[1].plot(mean_pr[:, 1, i], label=f'{class_name[i] if i in class_name else f"{i}"}', color=cmap(i))
        axs[1].set_title('Recall')
        axs[1].set_xlabel('Registration Rate [%]')
        axs[1].set_ylabel('Recall')
        axs[1].legend()

        # ラベルとタイトルの設定
        plt.tight_layout()
        plt.show(block=True)

if __name__ == "__main__":
    main()
