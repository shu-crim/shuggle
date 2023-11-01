
import os
import datetime
from enum import Enum
import json
from functools import cmp_to_key


class Task:
    TASKS_DIR =r"./tasks"
    FILENAME_TASK_JSON = r"task.json"

    class AnswerValueType(Enum):
        real = 1
        integer = 2

    class DataType(Enum):
        train = 1
        valid = 2
        test = 3

    class Metric(Enum):
        Accuracy = 1
        MAE = 2

    class InputDataType(Enum):
        Image1ch = 1
        Image3ch = 2

    class TaskType(Enum):
        Quest = 1
        Contest = 2


    id: str
    name: str
    explanation: str
    start_date: datetime
    end_date: datetime
    answer_value_type: AnswerValueType
    metric: Metric
    input_data_type: InputDataType
    multi_input_data: bool
    type: TaskType = TaskType.Quest
    goal = 0
    timelimit_per_data: float = 1.0

    def __init__(self, task_id) -> None:
        try:
            task_json_path = os.path.join(Task.TASKS_DIR, task_id, Task.FILENAME_TASK_JSON)
            json_open = open(task_json_path, 'r', encoding='utf-8')
            task = json.load(json_open)
            task = task["info"]

            self.id = task["id"]
            self.name = task["name"]
            self.explanation = task["explanation"]
            self.start_date = datetime.datetime.strptime(task["start_date"], '%Y-%m-%d')
            self.end_date = datetime.datetime.strptime(task["end_date"], '%Y-%m-%d')
            self.answer_value_type = self.answerValueType(task["answer_value_type"])
            self.metric = self.metricType(task["metric"])
            self.input_data_type = self.inputDataType(task["input_data_type"])
            self.multi_input_data = task["multi_input_data"]
            if "type" in task:
                if task["type"] == "quest":
                    self.type = Task.TaskType.Quest
                elif task["type"] == "contest":
                    self.type = Task.TaskType.Contest
            if "goal" in task:
                self.goal = float(task["goal"])
            if "timelimit_per_data" in task:
                self.timelimit_per_data = float(task["timelimit_per_data"])
        except Exception as e:
            print(e)
            print(f"Taskを読み込めませんでした: {task_id}")

    @staticmethod
    def answerValueType(answer_value_type):
        if answer_value_type == "integer":
            return Task.AnswerValueType.integer
        elif answer_value_type == "real":
            return Task.AnswerValueType.real
        else:
            raise(ValueError("無効なanswer_value_type指定です。"))

    @staticmethod
    def metricType(metric:str) -> Metric:
        if metric == "Accuracy":
            return Task.Metric.Accuracy
        elif metric == "MAE":
            return Task.Metric.MAE
        else:
            raise(ValueError("無効なmetric指定です。"))

    @staticmethod
    def inputDataType(input_data_type:str) -> InputDataType:
        if input_data_type == "image-1ch":
            return Task.InputDataType.Image1ch
        elif input_data_type == "image-3ch":
            return Task.InputDataType.Image3ch
        else:
            raise(ValueError("無効なinput_data_type指定です。"))

    @staticmethod
    def GoalText(metric:Metric, goal):
        if metric == Task.Metric.Accuracy:
            goal_text = f'正解率 {goal*100:.1f} % 以上'
        elif metric == Task.Metric.MAE:
            goal_text = f'平均絶対誤差 {goal} 以下'
        return goal_text


class Stats:
    username : str
    datetime : datetime
    filename : str = ""
    train : list = []
    valid : list = []
    test : list = []
    message : str = ''
    memo : str = ''
    metric: Task.Metric
    goal: float

    # ユーザ成績のcsvファイルに書かれた1行の成績記録をもとにstatsを読み取る
    def __init__(self, user_stats_line:str, username, metric:Task.Metric, goal:float) -> None:
        self.username = username
        self.metric = metric
        self.goal = goal

        raw = user_stats_line.rstrip(os.linesep).split(",")
        
        try:
            self.datetime = datetime.datetime.strptime(raw[0] + " " + raw[1], "%Y/%m/%d %H:%M:%S")
        except:
            self.datetime = datetime.datetime(1984, 4, 22)

        try:
            self.filename = raw[2]
        except:
            self.filename = ''

        if metric == Task.Metric.Accuracy:
            try:
                self.train = float(raw[5])
            except:
                self.train = -1

            try:
                self.valid = float(raw[8])
            except:
                self.valid = -1

            try:
                self.test = float(raw[11])
            except:
                self.test = -1

            try:
                self.message = raw[12]
            except:
                self.message = ''

            try:
                self.memo = raw[13]
            except:
                self.memo = ''

        elif metric == Task.Metric.MAE:
            try:
                self.train = float(raw[3])
            except:
                self.train = -1

            try:
                self.valid = float(raw[4])
            except:
                self.valid = -1

            try:
                self.test = float(raw[5])
            except:
                self.test = -1

            try:
                self.message = raw[6]
            except:
                self.message = ''

            try:
                self.memo = raw[7]
            except:
                self.memo = ''


    @staticmethod
    def GetBestStats(stats:list):
        def compare(a:Stats, b:Stats):
            goal = a.goal
            train_a = a.train
            train_b = b.train
            valid_a = a.valid
            valid_b = b.valid
            if a.test >= 0:
                test = True
                test_a = a.test
                test_b = b.test
            else:
                test = False

            if a.metric == Task.Metric.MAE:
                # 高い方がよい値となるよう反転させる
                goal *= -1
                train_a *= -1
                train_b *= -1
                valid_a *= -1
                valid_b *= -1
                if test:
                    test_a *= -1
                    test_b *= -1
            
            # Goal達成チェック
            train_a_achieve = True if train_a >= goal else False
            train_b_achieve = True if train_b >= goal else False
            valid_a_achieve = True if valid_a >= goal else False
            valid_b_achieve = True if valid_b >= goal else False
            if test:
                test_a_achieve = True if test_a >= goal else False
                test_b_achieve = True if test_b >= goal else False

            # test>valid>trainの順で目標達成していること
            if test:
                if test_a_achieve and not test_b_achieve:
                    return 1 #a
                if not test_a_achieve and test_b_achieve:
                    return -1 #b
                
            if valid_a_achieve and not valid_b_achieve:
                return 1 #a
            if not valid_a_achieve and valid_b_achieve:
                return -1 #b
            
            if train_a_achieve and not train_b_achieve:
                return 1 #a
            if not train_a_achieve and train_b_achieve:
                return -1 #b
            
            # test>valid>trainの順で性能が高い方を優先
            if test:
                if test_a > test_b:
                    return 1 #a
                if test_a < test_b:
                    return -1 #b
                
            if valid_a > valid_b:
                return 1 #a
            if valid_a < valid_b:
                return -1 #b
            
            if train_a > train_b:
                return 1 #a
            if train_a < train_b:
                return -1 #b
            
            # 提出日時が新しい方を優先
            if a.datetime > b.datetime:
                return 1 #a
            if a.datetime < b.datetime:
                return -1 #b
            
            return 0 # 引き分け

        target_stats = []
        for item in stats:
            if item.train < 0 or item.valid < 0:
                continue
            target_stats.append(item)

        if len(target_stats) == 0:
            return None

        try:
            sorted_list = sorted(target_stats, key=cmp_to_key(compare))
            best_stats = sorted_list[-1]
        except:
            return None

        return best_stats



        