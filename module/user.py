import os
import datetime
import glob
import shutil

from module.task import Task, Stats

class User:
    USER_CSV_PATH = r"./data/users.csv"

    class UserData():
        id : str
        email : str
        pass_hash : str
        name : str
        key : str

        def __init__(self, id="", email="", pass_hash="", name="", key="") -> None:
            self.id = id
            self.email = email
            self.pass_hash = pass_hash
            self.name = name
            self.key = key


    @staticmethod
    def WriteUsersCsv(path:str, users:dict, must_backup:bool=True) -> bool:
        # バックアップをとる
        if os.path.exists(path):
            try:
                backup_dir = os.path.join(os.path.dirname(path), "backup")
                if not os.path.exists(backup_dir):
                    os.makedirs(backup_dir)
                shutil.copy2(path, os.path.join(backup_dir, datetime.datetime.now().strftime('users_%Y%m%d_%H%M%S_%f.csv')))
            except:
                if must_backup:
                    return False
                
        # ディレクトリが無ければ作成
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        
        # 上書き作成する
        try:
            with open(path, mode='w', encoding='utf-8') as f:
                f.write('email,id,name,key,pass-hash\n')
                for id, user_data in users.items():
                    f.write(f"{user_data.email},{id},{user_data.name},{user_data.key},{user_data.pass_hash}\n")
        except:
            return False
        
        return True


    @staticmethod
    def AddUsersCsv(path:str, id:str, email:str, name:str, pass_hash:str, key:str) -> bool:
        # ユーザデータを読み込む
        users = User.ReadUsersCsv(path)
        if users == None:
            users = {}

        # 重複チェック
        if id in users:
            return False

        # ユーザデータを追加する
        users[id] = User.UserData(id, email, pass_hash, name, key)

        # 書き込んで結果を返す
        return User.WriteUsersCsv(path, users, True if os.path.exists(path) else False)


    @staticmethod
    def UpdateUsersCsv(path:str, id:str, target:str, value:str) -> bool:
        users = User.ReadUsersCsv(path)
        if users == None:
            return False
        if not id in users:
            return False
        
        # 更新する
        if target == 'key':
            users[id].key = value
        elif target == 'name':
            users[id].name = value
        elif target == 'pass_hash':
            users[id].pass_hash = value
        elif target == 'email':
            users[id].email = value
        else:
            return False

        # 書き込んで結果を返す
        return User.WriteUsersCsv(path, users)


    @staticmethod
    def numAchievement(user_id:str):
        # ディレクトリの一覧を作成して走査
        dir_list_tasks = glob.glob(os.path.join(Task.TASKS_DIR, '**/'))
        for dir_task in dir_list_tasks:                    
            # ディレクトリ名を取得→タスクIDとして使う
            task_id = os.path.basename(os.path.dirname(dir_task))

            # ユーザの成績があれば読み込み
            # user_result_path = os.path.join(dir_task, Task.OUTPUT_DIR_NAME, Task.USER_RESULT_DIR_NAME, f"{user_id}.csv")
            # if os.path.exists(user_result_path):



    @staticmethod
    def ReadUsersCsv(path:str):
        users = {}
        try:
            with open(path, encoding='utf-8') as f:
                f.readline() # ヘッダを読み飛ばす
                while True:
                    line = f.readline()
                    if not line:
                        break
                    if len(line.rstrip().split(',')) != 5:
                        continue
                    email, id, name, key, pass_hash = line.rstrip().split(',')
                    users[id] = User.UserData(id, email, pass_hash, name, key)
        except:
            return {}

        return users



    @staticmethod
    def GetUserStats(task_id) -> {}:
        # Task情報からmetricを読み込む
        task = Task(task_id)
        
        # ユーザ情報を読み込む
        users = User.ReadUsersCsv(User.USER_CSV_PATH)

        file_paths = glob.glob(os.path.join(Task.TASKS_DIR, task_id, Task.OUTPUT_DIR_NAME, "user", "*.csv"))
        stats = {}
        for file_path in file_paths:
            user_id = os.path.splitext(os.path.basename(file_path))[0]
            if not user_id in users:
                continue
            user_name = users[user_id].name
            stats[user_id] = []
            
            with open(file_path, "r", encoding='utf-8') as csv_file:
                line = csv_file.readline() # ヘッダ読み飛ばし
                while True:
                    line = csv_file.readline()
                    if not line:
                        break

                    stats[user_id].append(Stats(line, user_name, task.metric, task.goal, user_id))

            # ひとつもstatsがなかった場合はキーを削除
            if len(stats[user_id]) == 0:
                stats.pop(user_id)

        return stats
