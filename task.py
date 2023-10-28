
import os
import datetime
from enum import Enum
import json


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

    id: str
    name: str
    explanation: str
    start_date: datetime
    end_date: datetime
    answer_value_type: AnswerValueType
    metric: Metric
    input_data_type: InputDataType
    multi_input_data: bool

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
