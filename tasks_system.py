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
import json
from task import Task, Log
import chardet


UPLOAD_DIR = r"./upload_dir"
OUTPUT_DIR = r"./output"
USER_MODULE_DIR_NAME = r"user_module"
TIMESTAMP_FILE_NAME = r"timestamp.txt"
FILENAME_DATASET_JSON = r"dataset.json"
PROC_TIMEOUT_SEC = 1


def UpdateTtimestamp(task_id):
    # ディレクトリが無ければ作成
    if not os.path.exists(os.path.join(OUTPUT_DIR, task_id)):
        os.makedirs(os.path.join(OUTPUT_DIR, task_id))

    with open(os.path.join(OUTPUT_DIR, task_id, TIMESTAMP_FILE_NAME), "w", encoding='utf-8') as f:
        f.write(datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))


def read_dataset(path_json, answer_value_type=int, multi_data:bool=False, data_type:Task.InputDataType=Task.InputDataType.Image3ch):
    json_open = open(path_json, 'r', encoding='utf-8')
    dataset = json.load(json_open)

    filename_list = []
    input_data_list = [] #入力データ
    correct_list = [] #正解値
    num_problem = 0

    for item in dataset["data"]:
        try:
            # 正解値
            correct_list.append(answer_value_type(item["gt"]))

            # 入力データ
            data = []
            filename = []
            if multi_data:
                for path in item["path"]:
                    # 画像読み込み
                    filename.append(path)
                    data.append(np.array(Image.open(os.path.join(os.path.dirname(path_json), path))))
            else:
                # 画像読み込み
                filename = item["path"]
                data = np.array(Image.open(os.path.join(os.path.dirname(path_json), item["path"])))

            input_data = np.array(data, dtype=data[0].dtype)
            input_data_list.append(input_data)
            filename_list.append(filename)

            num_problem += 1
        except:
            print(f"入力データ({num_problem})の読み込みに失敗しました。")
            continue

    # 正解値リストをnumpyに変換
    correct_list = np.array(correct_list, dtype=answer_value_type)

    return num_problem, filename_list, input_data_list, correct_list


def evaluate(num_problem, input_data_list, func_recognition, answer_value_type, timelimit_per_data=PROC_TIMEOUT_SEC):
    total_proc_time = 0
    try:
        # ユーザ作成の処理にかける
        answer_list = np.zeros((num_problem), answer_value_type)
        with Pool(processes=1) as p:
            for i in range(num_problem):
                num_input_data = input_data_list[i].shape[0]
                time_limit = timelimit_per_data * (num_input_data + 20) if i == 0 else timelimit_per_data * num_input_data # 初回のみオーバーヘッドを考慮してゆるめ

                start_time = time.time()
                apply_result = p.apply_async(func_recognition, (input_data_list[i],))
                answer = apply_result.get(timeout=time_limit)

                # 返り値の型を矯正
                answer = answer_value_type(answer)
                if type(answer) is not answer_value_type:
                    print(f"Type error answer:{type(answer)} answer_value_type:{answer_value_type}")
                    raise(ValueError("推定処理の返り値の型が適切ではありません。"))
                
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
    
    return answer_list, total_proc_time


class Result:
    data_type = Task.DataType.train
    filename = ""
    correct = 0
    answer = 0

    def __init__(self, data_type, filename, correct, answer) -> None:
        self.data_type = data_type
        self.filename = filename
        self.correct = correct
        self.answer = answer
    

def evaluate3data(task_id, module_name, user_name, answer_value_type=int, multi_data:bool=False, data_type:Task.InputDataType=Task.InputDataType.Image3ch, contest:bool=False, timelimit_per_data=PROC_TIMEOUT_SEC):
    try:
        # ユーザ作成の処理を読み込む
        user_module = importlib.import_module(f"{USER_MODULE_DIR_NAME}.{task_id}.{module_name}")
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
        num_train, filename_list, input_data_list, correct_list = read_dataset(
            os.path.join(Task.TASKS_DIR, task_id, "train", FILENAME_DATASET_JSON), answer_value_type, multi_data, data_type)

        answer_list, total_proc_time = evaluate(num_train, input_data_list, func_recognition, answer_value_type, timelimit_per_data)
        if num_train == 0:
            return []
        for i in range(num_train):
            result = Result(Task.DataType.train, filename_list[i], correct_list[i], answer_list[i])
            result_list.append(result)
        print(f'Train({user_name}) average proc time: {total_proc_time / num_train : .1f}s, totla: {total_proc_time : .1f} s')

        # valid
        num_valid, filename_list, input_data_list, correct_list = read_dataset(
            os.path.join(Task.TASKS_DIR, task_id, "valid", FILENAME_DATASET_JSON), answer_value_type, multi_data, data_type)
        
        answer_list, total_proc_time = evaluate(num_valid, input_data_list, func_recognition, answer_value_type, timelimit_per_data)
        if num_valid == 0:
            return []
        for i in range(num_valid):
            result = Result(Task.DataType.valid, filename_list[i], correct_list[i], answer_list[i])
            result_list.append(result)
        print(f'Valid({user_name}) average proc time: {total_proc_time / num_valid : .1f}s, totla: {total_proc_time : .1f} s')

        # test
        if contest:
            num_test, filename_list, input_data_list, correct_list = read_dataset(
                os.path.join(Task.TASKS_DIR, task_id, "test", FILENAME_DATASET_JSON), answer_value_type, multi_data, data_type)
        
            answer_list, total_proc_time = evaluate(num_test, input_data_list, func_recognition, answer_value_type, timelimit_per_data)
            if num_test == 0:
                return []
            for i in range(num_test):
                result = Result(Task.DataType.test, filename_list[i], correct_list[i], answer_list[i])
                result_list.append(result)
            print(f'Test({user_name}) average proc time: {total_proc_time / num_test : .1f}s, totla: {total_proc_time : .1f} s')

    except Exception as e:
        raise(e)

    print(f'Proc Time({user_name}): {time.time()-start : .1f} s')

    return result_list


def ProcOneUser(task_id, user_name, new_filename, now, memo=''):
    # タスク情報の読み込み
    task:Task = Task(task_id)
    if task is None:
        print("タスク情報を読み込めません: {task_id}")
        return

    # 処理と評価を実行
    proc_success = False
    message = ''
    try:
        if task.answer_value_type == Task.AnswerValueType.integer:
            answer_value_type = int
        elif task.answer_value_type == Task.AnswerValueType.real:
            answer_value_type = float

        result_list = evaluate3data(
            task_id, os.path.splitext(new_filename)[0], # 拡張子を除く
            user_name, answer_value_type, task.multi_input_data,
            task.input_data_type, True if task.type == Task.TaskType.Contest else False,
            task.timelimit_per_data)

        proc_success = True
    except Exception as e:
        proc_success = False
        message = e
        print(f'evaluate3data: {e}')

    if proc_success:
        # 評価結果を集計
        if task.metric == Task.Metric.Accuracy:
            num_true = {}
            num_false = {}
            for data_type in Task.DataType:
                num_true[data_type] = 0
                num_false[data_type] = 0

            for result in result_list:
                if result.correct == result.answer:
                    num_true[result.data_type] += 1
                else:
                    num_false[result.data_type] += 1
        elif task.metric == Task.Metric.MAE:
            abs_errors = {}
            for result in result_list:
                if not result.data_type in abs_errors:
                    abs_errors[result.data_type] = []
                abs_errors[result.data_type].append(np.abs(result.answer - result.correct))

        # 評価結果の詳細を出力
        output_csv_filename = user_name + "_" + now.strftime('%Y%m%d_%H%M%S') + ".csv"
        with open(os.path.join(OUTPUT_DIR, task_id, "detail", output_csv_filename), "w", encoding='utf-8') as output_csv_file:
            # 集計
            output_csv_file.write(f"filename,{os.path.basename(new_filename)}\n\n")
            output_csv_file.write("type,num_data,{0}\n".format(
                    "true,false,accuracy" if task.metric == Task.Metric.Accuracy else ("MAE" if task.metric == Task.Metric.MAE else "")
                ))
            for data_type in Task.DataType:
                if task.metric == Task.Metric.Accuracy:
                    num_data = num_true[data_type] + num_false[data_type]
                    output_csv_file.write(f"{data_type.name},{num_data},{num_true[data_type]},{num_false[data_type]},{num_true[data_type]/num_data if num_data > 0 else '-'}\n")
                    # print(f"{data_type.name},{num_data},{num_true[data_type]},{num_false[data_type]},{num_true[data_type]/num_data if num_data > 0 else '-'}")
                elif task.metric == Task.Metric.MAE:
                    if data_type in abs_errors:
                        num_data = len(abs_errors[data_type])
                        output_csv_file.write(f"{data_type.name},{num_data},{np.average(np.array(abs_errors[data_type], float))}\n")

            # 詳細
            output_csv_file.write("\n")
            if task.metric == Task.Metric.Accuracy:
                output_csv_file.write("type,filename,correct,answer,check\n")
                for result in result_list:
                    output_csv_file.write(f"{result.data_type.name},{result.filename.replace(',', '-')},{result.correct},{result.answer},{1 if result.correct == result.answer else 0}\n")
            elif task.metric == Task.Metric.MAE:
                output_csv_file.write("type,filename,correct,answer,abs_error\n")
                for result in result_list:
                    output_csv_file.write(f"{result.data_type.name},{str(result.filename).replace(',', '-')},{result.correct},{result.answer},{np.abs(result.answer - result.correct)}\n")

    # ユーザ毎の結果出力
    csv_path = os.path.join(OUTPUT_DIR, task_id, "user", user_name + ".csv")
    if not os.path.exists(csv_path):
        # ファイルが無いのでヘッダを付ける
        with open(csv_path, "w", encoding='utf-8') as output_csv_file:
            output_csv_file.write("date,time,filename,")

            for data_type in Task.DataType:
                if task.metric == Task.Metric.Accuracy:
                    output_csv_file.write(f"{data_type.name}_true,{data_type.name}_false,{data_type.name}_accuracy,")
                elif task.metric == Task.Metric.MAE:
                    output_csv_file.write(f"{data_type.name}_MAE,")

            output_csv_file.write("message,memo")

    with open(csv_path, "a", encoding='utf-8') as output_csv_file:
        output_csv_file.write('\n') # 各結果の最初に改行を入れる。前の不正終了を引きずらないため
        output_csv_file.write(now.strftime('%Y/%m/%d,%H:%M:%S,'))                    
        output_csv_file.write(os.path.basename(new_filename) + ",")
        for data_type in Task.DataType:
            if task.metric == Task.Metric.Accuracy:
                if proc_success:
                    if data_type in num_true and data_type in num_false:
                        num_data = num_true[data_type] + num_false[data_type]
                        output_csv_file.write(f"{num_true[data_type]},{num_false[data_type]},{num_true[data_type]/num_data if num_data > 0 else '-'},")
                    else:
                        output_csv_file.write(f"-,-,-,")
                else:
                    output_csv_file.write(f"-,-,-,")
            elif task.metric == Task.Metric.MAE:
                if proc_success:
                    if data_type in abs_errors:
                        num_data = len(abs_errors[data_type])
                        if num_data > 0:
                            output_csv_file.write(f"{np.average(np.array(abs_errors[data_type], float))},")
                        else:
                            output_csv_file.write("-,")
                    else:
                        output_csv_file.write("-,")
                else:
                    output_csv_file.write("-,")

        output_csv_file.write(f"{message},{memo}")

    # 処理中であることを示すファイルを削除
    try:
        os.remove(os.path.join(OUTPUT_DIR, task_id, "user", f"{user_name}_inproc"))
    except:
        print(f"{user_name}_inproc を削除できませんでした。")

    # タイムスタンプ更新
    UpdateTtimestamp(task_id)

    # Log
    Log.write(f'{new_filename} on {task_id} {"was" if proc_success else "was not" } completed.')


def GetEncodingType(file):
    with open(file, 'rb') as f:
        rawdata = f.read()
    return chardet.detect(rawdata)['encoding']


def main():
    with ProcessPoolExecutor(max_workers=4) as proccess:
        while True:
            # ディレクトリの一覧を作成して走査
            dir_list_tasks = glob.glob(UPLOAD_DIR + '/**/')
            for dir_task in dir_list_tasks:                    
                # ディレクトリ名を取得→タスクIDとして使う
                task_id = os.path.basename(os.path.dirname(dir_task))

                # ディレクトリの一覧を作成して走査
                dir_list_users = glob.glob(dir_task + '/**/')
                for dir_user in dir_list_users:  
                    # ディレクトリ名を取得→ユーザ名として使う
                    user_name = os.path.basename(os.path.dirname(dir_user))

                    # ユーザのディレクトリ内の.pyファイルの一覧を作成して走査
                    py_files = glob.glob(os.path.join(dir_user, "*.py"))

                    if len(py_files) == 0:
                        continue
                    
                    path = py_files[0] # 最初に発見したファイルのみを対象とする

                    # モジュール移動先が無ければ生成(新規Taskの実行時)
                    dir_user_module = os.path.join("./", USER_MODULE_DIR_NAME, task_id)
                    if not os.path.exists(dir_user_module):
                        os.makedirs(dir_user_module)

                    # ファイルを読み込んで移動先に保存、元ファイルの削除を試みる
                    now = datetime.datetime.now()
                    new_filename = user_name + "_" + task_id + "_" + now.strftime('%Y%m%d_%H%M%S_') + os.path.basename(path)
                    try:
                        encoding = GetEncodingType(path)
                        with open(path, 'r', encoding=encoding) as f:
                            content = f.read()
                        with open(os.path.join(dir_user_module, new_filename), 'w', encoding='utf-8') as f:
                            f.write(content)
                        os.remove(path)
                    except:
                        continue

                    # メモもあれば読み込んで移動
                    memo = ''
                    if os.path.exists(path + '.txt'):
                        try:
                            with open(path + '.txt', encoding='utf-8') as f:
                                memo = f.read()

                            shutil.move(path + '.txt', os.path.join("./", USER_MODULE_DIR_NAME, task_id, new_filename + '.txt'))
                        except Exception as e:
                            print(f"read {path + '.txt'}: {e}")
                    
                    # 移動に成功したら評価
                    print(f"pcoccess start: {user_name}")
                    print(f"{path} -> {new_filename}")

                    # 出力先ディレクトリが存在しない場合は生成(新規Taskの実行時)
                    dir_output_user = os.path.join(OUTPUT_DIR, task_id, "user")
                    if not os.path.exists(dir_output_user):
                        os.makedirs(dir_output_user)

                    dir_output_detail = os.path.join(OUTPUT_DIR, task_id, "detail")
                    if not os.path.exists(dir_output_detail):
                        os.makedirs(dir_output_detail)

                    # 評価中であることを示すファイルを生成
                    with open(os.path.join(dir_output_user, f"{user_name}_inproc"), "w", encoding='utf-8') as f:
                        pass

                    # タイムスタンプ更新
                    UpdateTtimestamp(task_id)

                    # Log
                    Log.write(f'{user_name} submit {new_filename} to {task_id}, file movement succeeded, then the proccess started.')

                    # ファイルの移動に成功したらプロセス生成して処理開始
                    proccess.submit(ProcOneUser, task_id, user_name, new_filename, now, memo)


            # 少し待つ
            time.sleep(1.0)
            print(".")

if __name__ == "__main__":
    main()
