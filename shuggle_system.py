import os
import numpy as np
import importlib
from PIL import Image
from matplotlib import pyplot as plt
import glob
import shutil
import datetime
import time
from enum import Enum
from multiprocessing import Pool, TimeoutError
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


NUM_CLASS = 5
UPLOAD_DIR = r"./upload_dir"
USER_MODULE_DIR_NAME = r"user_module"
OUTPUT_DETAIL_DIR = r"./output/detail"
OUTPUT_EVERY_USER_DIR = r"./output/user"
INPUT_DATA_TRAIN_DIR = r"./input_data/train" 
INPUT_DATA_VALID_DIR = r"./input_data/valid" 
INPUT_DATA_TEST_DIR = r"./input_data/test"
CORRECT_ANSWER_CSV_FILENAME = r"correct_answer.csv"
PROC_TIMEOUT_SEC = 1


def read_dataset(path_csv):
    with open(path_csv, "r") as csv_file:
        filename_list = []
        input_data_list = [] #入力データ
        correct_list = [] #正解値
        while True:
            line = csv_file.readline()
            if not line:
                break

            try:
                filename, label = line.rstrip(os.linesep).split(",") # 画像ファイル名, 正解値
                correct_label = int(label)

                # 画像読み込み
                input_data_list.append(np.array(Image.open(os.path.join(os.path.dirname(path_csv), filename))))
                correct_list.append(correct_label) # 画像を読み込めたらラベルも追加
                filename_list.append(filename)
            except:
                print(f"{filename}の読み込みに失敗しました。")
                continue

    # リストをnumpyに変換
    correct_list = np.array(correct_list, dtype=int)

    return filename_list, input_data_list, correct_list


def evaluate(path_csv, func_recognition):
    # データ読み込み
    filename_list, input_data_list, correct_list = read_dataset(path_csv)

    # 正解データ数
    num_test = len(input_data_list)

    total_proc_time = 0
    try:
        # ユーザ作成の処理にかける
        answer_list = np.zeros((num_test), int)
        with Pool(processes=1) as p:
            for i in range(num_test):
                time_limit = PROC_TIMEOUT_SEC * 20 if i == 0 else PROC_TIMEOUT_SEC # 初回のみオーバーヘッドを考慮してゆるめ

                start_time = time.time()
                apply_result = p.apply_async(func_recognition, (input_data_list[i],))
                answer = apply_result.get(timeout=time_limit)

                if type(answer) is not int:
                    raise(ValueError("推定処理の返り値がint型ではありません。"))
                
                end_time = time.time()
                total_proc_time += end_time - start_time
                #print(f'proc time: {end_time - start_time} s')
                if end_time - start_time > time_limit:
                    raise(TimeoutError("推定処理がタイムアウトしました。"))

                answer_list[i] = answer
    except TimeoutError:
        print("推定処理がタイムアウトしました。")
        raise(TimeoutError("推定処理がタイムアウトしました。"))
    except Exception as e:
        raise(e)
    
    return num_test, filename_list, correct_list, answer_list, total_proc_time


class DataType(Enum):
    train = 1
    valid = 2
    test = 3


class Result:
    data_type = DataType.train
    filename = ""
    correct = 0
    answer = 0

    def __init__(self, data_type, filename, correct, answer) -> None:
        self.data_type = data_type
        self.filename = filename
        self.correct = correct
        self.answer = answer


def evaluate3data(module_name, user_name):
    try:
        # ユーザ作成の処理を読み込む
        user_module = importlib.import_module(f"{USER_MODULE_DIR_NAME}.{module_name}")
    except:
        raise(ValueError("モジュールを読み込めません。"))
    
    try:
        # ユーザ作成の処理を読み込む
        func_recognition = user_module.recognition
    except:
        raise(ValueError("関数recognition()を読み込めません。"))
    
    # 結果のリスト
    result_list = []
    
    start = time.time()

    try:    
        # train
        num_train, filename_list, correct_list, answer_list, total_proc_time = evaluate(os.path.join(INPUT_DATA_TRAIN_DIR, CORRECT_ANSWER_CSV_FILENAME), func_recognition)
        if num_train == 0:
            return []
        for i in range(num_train):
            result = Result(DataType.train, filename_list[i], correct_list[i], answer_list[i])
            result_list.append(result)
        print(f'Train({user_name}) average proc time: {total_proc_time / num_train : .1f}s, totla: {total_proc_time : .1f} s')

        # valid
        num_valid, filename_list, correct_list, answer_list, total_proc_time = evaluate(os.path.join(INPUT_DATA_VALID_DIR, CORRECT_ANSWER_CSV_FILENAME), func_recognition)
        if num_valid == 0:
            return []
        for i in range(num_valid):
            result = Result(DataType.valid, filename_list[i], correct_list[i], answer_list[i])
            result_list.append(result)
        print(f'Valud({user_name}) average proc time: {total_proc_time / num_valid : .1f}s, totla: {total_proc_time : .1f} s')

        # test
        num_test, filename_list, correct_list, answer_list, total_proc_time = evaluate(os.path.join(INPUT_DATA_TEST_DIR, CORRECT_ANSWER_CSV_FILENAME), func_recognition)
        if num_test == 0:
            return []
        for i in range(num_test):
            result = Result(DataType.test, filename_list[i], correct_list[i], answer_list[i])
            result_list.append(result)
        print(f'Test({user_name}) average proc time: {total_proc_time / num_test : .1f}s, totla: {total_proc_time : .1f} s')

    except Exception as e:
        raise(e)

    print(f'Proc Time({user_name}): {time.time()-start : .1f} s')

    return result_list


def ProcOneUser(user_name, new_filename, now):
    # 処理と評価を実行
    proc_success = False
    message = ""
    try:
        result_list = evaluate3data(os.path.splitext(new_filename)[0], user_name) # 拡張子を除く
        proc_success = True
    except Exception as e:
        proc_success = False
        message = e
        print(f'evaluate3data: {e}')

    if proc_success:
        # 評価結果を集計
        num_true = {}
        num_false = {}
        for data_type in DataType:
            num_true[data_type] = 0
            num_false[data_type] = 0

        for result in result_list:
            if result.correct == result.answer:
                num_true[result.data_type] += 1
            else:
                num_false[result.data_type] += 1

        # 評価結果の詳細を出力
        output_csv_filename = user_name + "_" + now.strftime('%Y%m%d_%H%M%S') + ".csv"
        with open(os.path.join(OUTPUT_DETAIL_DIR, output_csv_filename), "w", encoding='shift_jis') as output_csv_file:
            # 集計
            output_csv_file.write(f"filename,{os.path.basename(new_filename)}\n\n")
            output_csv_file.write("type,num_data,true,false,accuracy\n")
            for data_type in DataType:
                num_data = num_true[data_type] + num_false[data_type]
                output_csv_file.write(f"{data_type.name},{num_data},{num_true[data_type]},{num_false[data_type]},{num_true[data_type]/num_data if num_data > 0 else '-'}\n")
                print(f"{data_type.name},{num_data},{num_true[data_type]},{num_false[data_type]},{num_true[data_type]/num_data if num_data > 0 else '-'}")

            # 詳細
            output_csv_file.write("\n")
            output_csv_file.write("type,filename,correct,answer,check\n")
            for result in result_list:
                output_csv_file.write(f"{result.data_type.name},{result.filename},{result.correct},{result.answer},{1 if result.correct == result.answer else 0}\n")

    # ユーザ毎の結果出力
    csv_path = os.path.join(OUTPUT_EVERY_USER_DIR, user_name + ".csv")
    if not os.path.exists(csv_path):
        # ファイルが無いのでヘッダを付ける
        with open(csv_path, "w", encoding='shift_jis') as output_csv_file:
            output_csv_file.write("date,time,filename,")
            for data_type in DataType:
                output_csv_file.write(f"{data_type.name}_true,{data_type.name}_false,{data_type.name}_accuracy,")
            output_csv_file.write("message\n")

    with open(csv_path, "a", encoding='shift_jis') as output_csv_file:
        output_csv_file.write(now.strftime('%Y/%m/%d,%H:%M:%S,'))                    
        output_csv_file.write(os.path.basename(new_filename) + ",")
        for data_type in DataType:
            if proc_success:
                num_data = num_true[data_type] + num_false[data_type]
                output_csv_file.write(f"{num_true[data_type]},{num_false[data_type]},{num_true[data_type]/num_data if num_data > 0 else '-'},")
            else:
                output_csv_file.write(f"-,-,-,")

        output_csv_file.write(f"{message}")
        output_csv_file.write("\n")


def main():
    with ProcessPoolExecutor(max_workers=4) as proccess:
        while True:
            # ディレクトリの一覧を作成して走査
            dir_list = glob.glob(UPLOAD_DIR + '/**/')

            for dir in dir_list:
                # ディレクトリ名を取得→ユーザ名として使う
                user_name = os.path.basename(os.path.dirname(dir))

                # ユーザのディレクトリ内の.pyファイルの一覧を作成して走査
                py_files = glob.glob(os.path.join(UPLOAD_DIR, user_name, "*.py"))

                if len(py_files) == 0:
                    continue
                
                path = py_files[0] # 最初に発見したファイルのみを対象とする

                # ファイル移動を試みる
                now = datetime.datetime.now()
                new_filename = user_name + "_" + now.strftime('%Y%m%d_%H%M%S_') + os.path.basename(path)
                try:
                    shutil.move(path, os.path.join("./", USER_MODULE_DIR_NAME, new_filename))
                except:
                    continue
                
                # 移動に成功したら評価
                print(f"pcoccess start: {user_name}")
                print(f"{path} -> {new_filename}")

                # ファイルの移動に成功したらプロセス生成して処理開始
                proccess.submit(ProcOneUser, user_name, new_filename, now)


            # 少し待つ
            time.sleep(1.0)
            print(".")

if __name__ == "__main__":
    main()
