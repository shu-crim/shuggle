import os
import random
import numpy as np
from PIL import Image
import cv2
import json
import time

DIR_TASK = r"./tasks/task-z"
FILENAME_TASK_JSON = r"task.json"
FILEPATH_INPUT_DATA_JSON = r"train/dataset.json"


def answer_data_type(answer_value_type):
    if answer_value_type == "integer":
        return int
    elif answer_value_type == "real":
        return float
    else:
        return None


def read_task(path_json):
    json_open = open(path_json, 'r')
    task = json.load(json_open)

    return task["info"]


def read_dataset(path_json, answer_value_type=int, multi_data=False, input_data_type="image-3ch"):
    json_open = open(path_json, 'r')
    dataset = json.load(json_open)

    filename_list = []
    input_data_list = [] #���̓f�[�^
    correct_list = [] #����l
    num_problem = 0

    for item in dataset["data"]:
        try:
            # ����l
            correct_list.append(answer_value_type(item["gt"]))

            # ���̓f�[�^
            data = []
            filename = []
            if multi_data:
                for path in item["path"]:
                    # �摜�ǂݍ���
                    filename.append(path)
                    data.append(np.array(Image.open(os.path.join(os.path.dirname(path_json), path))))
            else:
                # �摜�ǂݍ���
                filename = item["path"]
                data.append(np.array(Image.open(os.path.join(os.path.dirname(path_json), item["path"]))))

            input_data = np.array(data, dtype=data[0].dtype)
            input_data_list.append(input_data)
            filename_list.append(filename)

            num_problem += 1
        except:
            print(f"���̓f�[�^({num_problem})�̓ǂݍ��݂Ɏ��s���܂����B")
            continue

    # ����l���X�g��numpy�ɕϊ�
    correct_list = np.array(correct_list, dtype=answer_value_type)

    return num_problem, filename_list, input_data_list, correct_list


def recognition(input_data) -> float:
    # �����ɏ���������
    time.sleep(0.9 * input_data.shape[0])

    # float�Ő���l��Ԃ�
    return np.random.uniform(0, 2)


def main():
    # �^�X�N���ǂݍ���
    task = read_task(os.path.join(DIR_TASK, FILENAME_TASK_JSON))
    answer_value_type = answer_data_type(task["answer_value_type"])
    if answer_value_type is None:
        return

    # �f�[�^�ǂݍ���
    num_problem, filename_list, input_data_list, correct_list = read_dataset(
        os.path.join(DIR_TASK, FILEPATH_INPUT_DATA_JSON), answer_value_type, task["multi_input_data"], task["input_data_type"])

    # ���[�U�쐬�̏����ɂ�����
    answer_list = np.zeros((num_problem), answer_value_type)
    for i in range(num_problem):
        answer_list[i] = recognition(input_data_list[i])

    # �]��
    print("correct_list", correct_list)
    print("answer_list", answer_list)

    if task["metric"] == "MAE":
        evaluate = np.abs(answer_list - correct_list)
        print("evaluate", evaluate)
        print(f"MAE: {np.average(evaluate)}")
    elif task["metric"] == "Accuracy":
        evaluate = answer_list == correct_list
        print("evaluate", evaluate)
        print(f"Accuracy: {np.sum(evaluate) / num_problem}")
    

if __name__ == "__main__":
    main()
