import os
import random
import numpy as np
from PIL import Image
import cv2

NUM_CLASS = 5
PATH_INPUT_DATA_CSV = r"./input_data/train/correct_answer.csv"

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


def recognition(input_data) -> int:
    # ここに処理を書く


    # 整数で推定クラスを返す
    return random.randint(1, NUM_CLASS)


def main():
    # データ読み込み
    filename_list, input_data_list, correct_list = read_dataset(PATH_INPUT_DATA_CSV)
    num_test = len(filename_list)

    # ユーザ作成の処理にかける
    answer_list = np.zeros((num_test), int)
    for i in range(num_test):
        answer_list[i] = recognition(input_data_list[i])

    # 答え合わせ
    evaluate = correct_list == answer_list
    print("correct_list", correct_list)
    print("answer_list", answer_list)
    print("evaluate", evaluate)
    print(f"accuracy: {np.sum(evaluate)/num_test*100:.2f}% ({np.sum(evaluate)} / {num_test})")
    

if __name__ == "__main__":
    main()
