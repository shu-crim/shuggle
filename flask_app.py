from flask import Flask, render_template, request, redirect, url_for, make_response, Markup, send_from_directory, send_file
from flask_httpauth import HTTPBasicAuth, HTTPDigestAuth
from werkzeug.utils import secure_filename
import json
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

import os
import glob
import datetime
from enum import Enum
import shutil

from task import Task


OUTPUT_DIR = r"./output"
UPLOAD_DIR_ROOT = r"./upload_dir"
ALLOWED_EXTENSIONS = set(['py'])
TASK = {}
SETTING = None
USER_CSV_PATH = r"./data/users.csv"
SETTING_JSON_PATH = r"./data/setting.json"
HASH_METHOD = "pbkdf2:sha256:260000"
USER_MODULE_DIR_NAME = r"user_module"


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


class Stats():
    username : str
    datetime : datetime
    filename : str = ""
    train : list = []
    valid : list = []
    test : list = []
    message : str = ''
    memo : str = ''


class Page(Enum):
    HOME = 0,
    TASK = 1,
    BOARD = 2,
    LOG = 3,
    UPLOAD = 4,
    ADMIN = 9


# Flaskオブジェクトの生成
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 #ファイルサイズ制限 2MB
app.config['SECRET_KEY'] = 'secret key here'
auth = HTTPDigestAuth()
auth_users = {
    "root": "password",
}


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
                users[id] = UserData(id, email, pass_hash, name, key)
    except:
        return {}

    return users


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


def AddUsersCsv(path:str, id:str, email:str, name:str, pass_hash:str, key:str) -> bool:
    # ユーザデータを読み込む
    users = ReadUsersCsv(path)
    if users == None:
        users = {}

    # 重複チェック
    if id in users:
        return False

    # ユーザデータを追加する
    users[id] = UserData(id, email, pass_hash, name, key)

    # 書き込んで結果を返す
    return WriteUsersCsv(path, users, True if os.path.exists(path) else False)


def UpdateUsersCsv(path:str, id:str, target:str, value:str) -> bool:
    users = ReadUsersCsv(path)
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
    return WriteUsersCsv(path, users)


def GetUserStats(task_id) -> {}:
    def TransIntIntFloat(true_false_accuracy : list):
        result = [0, 0, 0.0]
        try:
            result[0] = int(true_false_accuracy[0])
            result[1] = int(true_false_accuracy[1])
            result[2] = float(true_false_accuracy[2])
        except:
            return [-1, -1, -1] #評価不能は負値
        return result

    def TransFloat(num:str):
        try:
            result = float(num)
        except:
            return -1 #評価不能は負値
        return result
    
    # Task情報からmetricを読み込む
    metric = Task(task_id).metric
    
    # ユーザ情報を読み込む
    users = ReadUsersCsv(USER_CSV_PATH)

    file_paths = glob.glob(os.path.join(OUTPUT_DIR, task_id, "user", "*.csv"))
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

                raw = line.rstrip(os.linesep).split(",")
                if metric == Task.Metric.Accuracy:
                    if len(raw) < 13:
                        continue
                elif metric == Task.Metric.MAE:
                    if len(raw) < 7:
                        continue
                else:
                    print("不正なmetric指定:", metric)

                try:
                    dt = datetime.datetime.strptime(raw[0] + " " + raw[1], "%Y/%m/%d %H:%M:%S")
                    filename = raw[2]

                    if metric == Task.Metric.Accuracy:
                        train = TransIntIntFloat(raw[3:6])
                        valid = TransIntIntFloat(raw[6:9])
                        test = TransIntIntFloat(raw[9:12])
                        message = raw[12]
                        memo = raw[13] if len(raw) >= 14 else ""
                    elif metric == Task.Metric.MAE:
                        train = TransFloat(raw[3])
                        valid = TransFloat(raw[4])
                        test = TransFloat(raw[5])
                        message = raw[6]
                        memo = raw[7] if len(raw) >= 8 else ""

                    # すべて読めたので保持
                    stats_read = Stats()
                    stats_read.username = user_name
                    stats_read.datetime = dt
                    stats_read.filename = filename
                    stats_read.train = train
                    stats_read.valid = valid
                    stats_read.test = test
                    stats_read.message = message
                    stats_read.memo = memo
                    stats[user_id].append(stats_read)
                except Exception as e:
                    print(e)
                    print("statsを読み込めませんでした。")

        # ひとつも読めなかった場合はキーを削除
        if len(stats[user_id]) == 0:
            stats.pop(user_id)

    return stats


def menuHTML(page, task_id="", url_from=""):
    html = """
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">IR <span style="color:#00a497">T</span>asks</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarSupportedContent">
                    <ul class="navbar-nav me-auto mb-2 mb-lg-0">
    """

    if page != Page.HOME:
        html += """
                        <li class="nav-item">
                            <a class="nav-link{1} href="/{6}/task">{0}</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{2} href="/{6}/board">評価結果</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{3} href="/{6}/log">履歴</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{4} href="/{6}/upload">提出</a>
                        </li>
                        {5}
        """.format(
            TASK[task_id].name,
            " active\" aria-current=\"page\"" if page == Page.TASK else "\"",
            " active\" aria-current=\"page\"" if page == Page.BOARD else "\"",
            " active\" aria-current=\"page\"" if page == Page.LOG else "\"",
            " active\" aria-current=\"page\"" if page == Page.UPLOAD else "\"",
            """
                        <li class="nav-item">
                            <a class="nav-link active">管理者</a>
                        </li>
            """ if page == Page.ADMIN else "",
            task_id
        )

    html += f"""
                    </ul>
                    <ul class="navbar-nav ml-auto mb-2 mb-lg-0">
                        <li class="nav-item">
                            <a id="login-user-name" class="nav-link active" aria-current="page" href="/user/info{'?from=' + url_from if url_from != '' else ''}"></a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    """

    return Markup(html)


def EvaluatedValueStyle(metric:Task.Metric, evaluated_value, goal) -> str:
    achieve = False
    if metric == Task.Metric.Accuracy:
        if evaluated_value >= goal:
            achieve = True
    elif metric == Task.Metric.MAE:
        if evaluated_value <= goal:
            achieve = True
    
    return ' style="color:#0dcaf0"' if achieve else ''


def Achieve(metric:Task.Metric, goal, train, valid, test=None):
    result = '<span style="color:#0dcaf0">★</span>'
    if metric == Task.Metric.Accuracy:
        if train < goal or valid < goal or (test is not None and test < goal):
            result = ''
    elif metric == Task.Metric.MAE:
        if train > goal or valid > goal or (test is not None and test > goal):
            result = ''

    return result


def CreateTableRow(stats, metric:Task.Metric, goal_value=None, test=False, message=False, memo=False, visible_invalid_result=False):
    html_user = ""
    html_user += f'<tr>'
    html_user += f'<td>{stats.username}</td>'
    html_user += f'<td>{stats.datetime}</td>'

    html_temp = ""
    if metric == Task.Metric.Accuracy:
        if stats.train[0] < 0:
            if visible_invalid_result:
                html_temp += ('<td>-</td><td>-</td><td>-</td>' if test else '<td>-</td><td>-</td>')
            else:
                return ""
        else:
            html_temp += f'<td{EvaluatedValueStyle(metric, stats.train[2], goal_value)}>{stats.train[2] * 100:.2f} %</td>' if stats.train[0] + stats.train[1] > 0 else '<td>0.00 %</td>'
            html_temp += f'<td{EvaluatedValueStyle(metric, stats.valid[2], goal_value)}>{stats.valid[2] * 100:.2f} %</td>' if stats.valid[0] + stats.valid[1] > 0 else '<td>0.00 %</td>'
            if test:
                html_temp += f'<td{EvaluatedValueStyle(metric, stats.test[2], goal_value)}>{stats.test[2] * 100:.2f} %</td>' if stats.test[0] + stats.test[1] > 0 else '<td>0.00 %</td>'
    
    elif metric == Task.Metric.MAE:
        if stats.train < 0:
            if visible_invalid_result:
                html_temp += ('<td>-</td><td>-</td><td>-</td>' if test else '<td>-</td><td>-</td>')
            else:
                return ""
        else:
            try:
                html_temp += f'<td{EvaluatedValueStyle(metric, stats.train, goal_value)}>{stats.train:.3f}</td>'
                html_temp += f'<td{EvaluatedValueStyle(metric, stats.valid, goal_value)}>{stats.valid:.3f}</td>'
                if test:
                    html_temp += f'<td{EvaluatedValueStyle(metric, stats.test, goal_value)}>{stats.test:.3f}</td>'
            except:
                html_temp += ('<td>-</td><td>-</td><td>-</td>' if test else '<td>-</td><td>-</td>')

    html_user += html_temp

    if memo:
        html_user += f'<td>{stats.memo}</td>'
    if message:
        html_user += f'<td>{stats.message}</td>'
    html_user += f'</tr>'

    return html_user


def CreateTable(stats_list, metric:Task.Metric, goal=None, test=False, message=False, memo=False):
    def metricName(metric: Task.Metric):
        if metric == Task.Metric.Accuracy:
            return '正解率'
        elif metric == Task.Metric.MAE:
            return '平均絶対誤差'
        else:
            return ''

    num_col = 0
    html_table = ""
    html_table += "<table class=\"table table-dark\" id=\"fav-table\">"
    html_table += "<thead><tr>"
    html_table += f"<th id=\"th-{num_col}\">参加者</th>"
    num_col += 1
    html_table += f"<th id=\"th-{num_col}\">提出日時</th>"
    num_col += 1
    html_table += f"<th id=\"th-{num_col}\">train(配布){metricName(metric)}</th>"
    num_col += 1
    html_table += f"<th id=\"th-{num_col}\">valid{metricName(metric)}</th>"
    num_col += 1
    if test:
        html_table += f"<th id=\"th-{num_col}\">test{metricName(metric)}</th>"
        num_col += 1
    if memo:
        html_table += f"<th id=\"th-{num_col}\">メモ</th>"
        num_col += 1
    if message:
        html_table += f"<th id=\"th-{num_col}\">メッセージ</th>"
        num_col += 1
    html_table += "</tr></thead>"
    html_table += "<tbody>"

    for stats in stats_list:
        html_table += CreateTableRow(stats, metric, goal, test=test, message=message, memo=memo)

    html_table += "</tbody>"
    html_table += "</table>"

    return html_table, num_col


def CreateInProcHtml(task_id):
    # ユーザ情報を読み込む
    users = ReadUsersCsv(USER_CSV_PATH)

    inproc_text = ''
    for user_id in users:
        if os.path.exists(os.path.join(OUTPUT_DIR, task_id, "user", f"{user_id}_inproc")):
            inproc_text += f"{users[user_id].name} さんの評価を実行中です。<br>"

    return inproc_text + '<br>'


def CreateMyTaskTable(user_id) -> str:
    INIT_ERROR = 100000000
    submits = []

    # user_idのstatsをTaskごとに取得
    for task_id, task in TASK.items():
        task:Task = task
        stats_temp = GetUserStats(task_id)
        if user_id in stats_temp:
            min_error = INIT_ERROR
            hold_submit:Submit = Submit()
            hold_submit.task_id = task.id
            hold_submit.task_name = task.name
            hold_submit.metric = task.metric
            hold_submit.task_type = task.type
            hold_submit.goal = task.goal

            for item in stats_temp[user_id]:
                stats:Stats = item
                error = min_error
                if task.type == Task.TaskType.Contest:
                    # コンテストではTestの成績ベストを選択
                    if task.metric == Task.Metric.Accuracy:
                        if stats.test[2] < 0:
                            continue
                        error = 1 - stats.test[2]
                    elif task.metric == Task.Metric.MAE:
                        if stats.test < 0:
                            continue
                        error = stats.test
                elif task.type == Task.TaskType.Quest:
                    # クエストではValidの成績ベストを選択
                    if task.metric == Task.Metric.Accuracy:
                        if stats.valid[2] < 0:
                            continue
                        error = 1 - stats.valid[2]
                    elif task.metric == Task.Metric.MAE:
                        if stats.valid < 0:
                            continue
                        error = stats.valid

                if error < min_error:
                    hold_submit.stats = item
                    min_error = error
                
            if min_error != INIT_ERROR:
                submits.append(hold_submit)

    # 提出日時でソート
    sorted_submits = sorted(submits, key=lambda x: x.stats.datetime, reverse=True)
    
    # 表のHTMLを作成
    html_table = '<table class="table table-dark">'
    html_table += "<thead><tr>"
    html_table += "<th>提出日時</th>"
    html_table += "<th>Task</th>"
    html_table += "<th>Goal</th>"
    html_table += "<th>train</th>"
    html_table += "<th>valid</th>"
    html_table += "<th>test</th>"
    html_table += "</tr></thead>"
    html_table += "<tbody>"

    for submit in sorted_submits:
        html_table += CreateSubmitTableRow(submit, goal=True, test=True, memo=False, message=False)

    html_table += "</tbody>"
    html_table += "</table>"

    return html_table


class Submit:
    stats: Stats
    task_id: str
    task_name: str
    metric: Task.Metric
    task_type: Task.TaskType
    goal: float


def CreateSubmitTableRow(submit:Submit, visible_invalid_data:bool=False, goal=False, test=False, memo:bool=True, message:bool=True):
    try:
        html_submit = ""
        html_submit += f'<tr>'
        html_submit += f'<td><a href="/source/{submit.task_id}/{submit.stats.filename}" class="link-info">{submit.stats.datetime}</a></td>'
        html_submit += f'<td><a href="/{submit.task_id}/task" class="link-info">{submit.task_name}</a></td>'

        html_temp = ""
        if submit.metric == Task.Metric.Accuracy:
            if goal:
                html_temp += f'<td>{submit.goal*100:.0f} &percnt; 以上 {Achieve(submit.metric, submit.goal, submit.stats.train[2], submit.stats.valid[2], submit.stats.test[2] if submit.task_type == Task.TaskType.Contest else None)}</td>'
            if submit.stats.train[0] < 0:
                if visible_invalid_data:
                    html_temp += '<td>-</td><td>-</td>' if not test else '<td>-</td><td>-</td><td>-</td>'
                else:
                    return ""
            else:
                html_temp += f'<td{EvaluatedValueStyle(submit.metric, submit.stats.train[2], submit.goal)}>{submit.stats.train[2] * 100:.2f} &percnt;</td>' if submit.stats.train[0] + submit.stats.train[1] > 0 else '<td>0.00 &percnt;</td>'
                html_temp += f'<td{EvaluatedValueStyle(submit.metric, submit.stats.valid[2], submit.goal)}>{submit.stats.valid[2] * 100:.2f} &percnt;</td>' if submit.stats.valid[0] + submit.stats.valid[1] > 0 else '<td>0.00 &percnt;</td>'
                if test:
                    if submit.task_type == Task.TaskType.Quest:
                        html_temp += '<td>-</td>'
                    elif submit.task_type == Task.TaskType.Contest:
                        html_temp += f'<td{EvaluatedValueStyle(submit.metric, submit.stats.test[2], submit.goal)}>{submit.stats.test[2] * 100:.2f} &percnt;</td>' if submit.stats.test[0] + submit.stats.test[1] > 0 else '<td>0.00 &percnt;</td>'
        
        elif submit.metric == Task.Metric.MAE:
            if goal:
                html_temp += f'<td>MAE {submit.goal:.1f} 以下 {Achieve(submit.metric, submit.goal, submit.stats.train, submit.stats.valid, submit.stats.test if submit.task_type == Task.TaskType.Contest else None)}</td>'
            try:
                if submit.stats.train < 0:
                    if visible_invalid_data:
                        html_temp += '<td>-</td><td>-</td>' if not test else '<td>-</td><td>-</td><td>-</td>'
                    else:
                        return ""
                else:
                    html_temp += f'<td{EvaluatedValueStyle(submit.metric, submit.stats.train, submit.goal)}>{submit.stats.train:.3f}(MAE)</td>'
                    html_temp += f'<td{EvaluatedValueStyle(submit.metric, submit.stats.valid, submit.goal)}>{submit.stats.valid:.3f}(MAE)</td>'
                    if test:
                        if submit.task_type == Task.TaskType.Quest:
                            html_temp += '<td>-</td>'
                        elif submit.task_type == Task.TaskType.Contest:
                            html_temp += f'<td{EvaluatedValueStyle(submit.metric, submit.stats.test, submit.goal)}>{submit.stats.test:.3f}(MAE)</td>'
            except:
                html_temp += '<td>-</td><td>-</td>'

        html_submit += html_temp

        if memo:
            html_submit += f'<td>{submit.stats.memo}</td>'
        if message:
            html_submit += f'<td>{submit.stats.message}</td>'

        html_submit += f'</tr>'
    except Exception as e:
        print(e)
        return ""

    return html_submit


def CreateSubmitTable(user_id) -> str:
    submits = []

    # user_idのstatsをTaskごとに取得
    for task_id, task in TASK.items():
        stats_temp = GetUserStats(task_id)
        if user_id in stats_temp:
            for item in stats_temp[user_id]:
                submit: Submit = Submit()
                submit.stats = item
                submit.task_id = task.id
                submit.task_name = task.name
                submit.metric = task.metric
                submit.task_type = task.type
                submit.goal = task.goal
                submits.append(submit)

    # 提出日時でソート
    sorted_submits = sorted(submits, key=lambda x: x.stats.datetime, reverse=True)
    
    # 表のHTMLを作成
    html_table = '<table class="table table-dark">'
    html_table += "<thead><tr>"
    html_table += "<th>提出日時</th>"
    html_table += "<th>Task</th>"
    html_table += "<th>train</th>"
    html_table += "<th>valid</th>"
    html_table += "<th>メモ</th>"
    html_table += "<th>メッセージ</th>"
    html_table += "</tr></thead>"
    html_table += "<tbody>"

    for submit in sorted_submits:
        html_table += CreateSubmitTableRow(submit, True)

    html_table += "</tbody>"
    html_table += "</table>"

    return html_table


def VerifyEmailAndPassword(email, password):
    # ユーザ情報を読み込む
    users = ReadUsersCsv(USER_CSV_PATH)
    
    # 認証を行う
    verified = False
    user_data = None
    for id, user_data in users.items():
        if user_data.email == email:
            pass_hash = user_data.pass_hash
            if check_password_hash(pass_hash, password):
                verified = True
            break
    
    return verified, user_data


def VerifyIdAndKey(user_id, user_key):
    # ユーザ情報を読み込む
    users = ReadUsersCsv(USER_CSV_PATH)
    
    # 認証を行う
    verified = False
    if user_id in users:
        user_data = users[user_id]
        if user_data.key == user_key:
            verified = True
    else:
        user_data = UserData()

    return verified, user_data


@auth.get_password
def get_pw(username):
    if username in auth_users:
        return auth_users.get(username)
    return None


@app.route('/')
def index():
    today = datetime.datetime.now()
    task_list_quest = []
    task_list_open = []
    task_list_closed = []
    task_list_prepare = []
    for key, value in TASK.items():
        task:Task = value
        info = {
            'id': key,
            'name': task.name,
            'explanation': task.explanation
        }

        if value.start_date <= today:
            # スタート後
            if task.type == Task.TaskType.Quest:
                # Questはいつでも開かれている
                task_list_quest.append(info)
            elif task.type == Task.TaskType.Contest:
                # Contestは開催期間により振り分け
                if value.end_date > today:
                    task_list_open.append(info)
                else:
                    task_list_closed.append(info)
        else:
            # スタート前
            task_list_prepare.append(info)
    
    return render_template('index.html', task_list_open=task_list_open, task_list_closed=task_list_closed, task_list_quest=task_list_quest, task_list_prepare=task_list_prepare, name_contest=SETTING["name"]["contest"], menu=menuHTML(Page.HOME, url_from="/"))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'), 'favicon.ico', )


@app.route('/join', methods=['GET', 'POST'])
def join():
    from_url = request.args.get('from')
    if from_url is None:
        from_url = "/"

    if request.method == 'GET':
        return render_template(f'join.html', from_url=from_url, message="")
    
    elif request.method == 'POST':
        try:
            email = request.form['inputEmail']
            password = request.form['inputPassword']
            password_verify = request.form['inputPasswordVerify']
            next_url = request.form['nextUrl']
        except:
            return render_template(f'join.html', from_url=from_url, message="入力データを受け取れませんでした。")
        
        # 2つのパスワード入力の一致チェック
        if password != password_verify:
            return render_template(f'join.html', from_url=from_url, message="再入力したパスワードが一致していません。")
        
        # ユーザ情報を読み込む
        users = ReadUsersCsv(USER_CSV_PATH)

        # email重複チェック
        duplicate = False
        for user_id, user_data in users.items():
            if email == user_data.email:
                duplicate = True
                break
        if duplicate:
            return render_template(f'join.html', from_url=from_url, message="そのEmail addressは既に登録されています。")
        
        # ID発行
        user_id = ""
        for i in range(10000):
            id = str(uuid.uuid4()).split('-')[0]
            if id in users:
                continue
            else:
                user_id = id
                break

        if user_id == "":
            return render_template(f'join.html', from_url=from_url, message="IDを発行できませんでした。")
        
        # パスワードをハッシュ化
        pass_hash = generate_password_hash(password, salt_length=21)
        
        # 本人確認用のキーを作成
        user_key = str(uuid.uuid4()).split('-')[0]

        # ユーザ登録
        name = email.split('@')[0]
        success = AddUsersCsv(USER_CSV_PATH, user_id, email, name, pass_hash, user_key)

        if not success:
            return render_template(f'join.html', from_url=from_url, message="ユーザ情報を登録できませんでした。")

        return render_template(f'user.html', from_url=from_url, user_email=email, user_id=user_id, user_key=user_key, user_name=name, next_url=next_url, login="true", update_user_data="true")


@app.route('/login', methods=['GET', 'POST'])
def login():
    from_url = request.args.get('from')
    if from_url is None:
        from_url = "/"

    if request.method == 'GET':
        return render_template(f'login.html', from_url=from_url, message="", email_admin=SETTING["admin"]["email"])
    
    elif request.method == 'POST':
        try:
            email = request.form['inputEmail']
            password = request.form['inputPassword']
            next_url = request.form['nextUrl']
        except:
            return render_template(f'login.html', from_url=from_url, message="入力データを受け取れませんでした。", email_admin=SETTING["admin"]["email"])
        
        # emailとパスワードで照合
        verified, user_data = VerifyEmailAndPassword(email, password)
        if not verified:
            return render_template(f'login.html', from_url=from_url, message="Email addressかPasswordが誤っています。", email_admin=SETTING["admin"]["email"])

        # 認証OKなので本人確認用のキーを作成して渡す
        user_key = str(uuid.uuid4()).split('-')[0]

        # キーを保存
        UpdateUsersCsv(USER_CSV_PATH, user_data.id, 'key', user_key)

        return render_template(f'user.html', from_url=from_url, user_email=email, user_id=user_data.id, user_key=user_key, user_name=user_data.name, next_url=next_url, login="true", update_user_data="true")


@app.route('/user/info', methods=['GET', 'POST'])
def user():
    if request.method == 'GET':
        from_url = request.args.get('from')
        return render_template(f'user.html', login="false", from_url=from_url if from_url is not None else "/")

    elif request.method == 'POST':
        try:
            user_id = request.form['userID']
            user_key = request.form['userKey']
            verified, user_data = VerifyIdAndKey(user_id, user_key)
            if not verified:
                raise(ValueError())
        except:
            return render_template(f'user.html', message='ユーザ認証に失敗しました。')
        
        new_name = ''
        message = ''
        try:
            if 'buttonChangeName' in request.form:
                # 名前を変更
                new_name = request.form['newName']
                success = UpdateUsersCsv(USER_CSV_PATH, user_id, 'name', new_name)
                if not success:
                    message = 'ユーザ情報の更新に失敗しました。'
                    raise(ValueError())
                message = 'ユーザ名を変更しました。'
            elif 'buttonChangePassword' in request.form:
                # パスワードを変更
                password = request.form['inputPassword']
                password_verify = request.form['inputPasswordVerify']
                # 2つのパスワード入力の一致チェック
                if password != password_verify:
                    message = '再入力したパスワードが一致していません。'
                    raise(ValueError())
                # パスワードをハッシュ化
                pass_hash = generate_password_hash(password, salt_length=21)
                success = UpdateUsersCsv(USER_CSV_PATH, user_id, 'pass_hash', pass_hash)
                if not success:
                    message = 'ユーザ情報の更新に失敗しました。'
                    raise(ValueError())
                message = 'パスワードを変更しました。'
        except:
            return render_template(f'user.html', message=message)

        return render_template(f'user.html', user_name=new_name, update_user_data="true", message=message)


@app.route('/my-task-table/<user_id>/<user_key>')
def my_task_table(user_id, user_key):
    # 認証
    verified, user_data = VerifyIdAndKey(user_id, user_key)
    if not verified:
        return redirect(url_for('login'))
    
    # 提出Taskテーブルを作成
    table_html = CreateMyTaskTable(user_id)

    return table_html


@app.route('/submit-table/<user_id>/<user_key>')
def submit_table(user_id, user_key):
    # 認証
    verified, user_data = VerifyIdAndKey(user_id, user_key)
    if not verified:
        return redirect(url_for('login'))
    
    # 提出テーブルを作成
    table_html = CreateSubmitTable(user_id)

    return table_html


@app.route('/source/<task_id>/<filename>')
def source(task_id, filename):
    file_path = os.path.join(USER_MODULE_DIR_NAME, task_id, filename)
    if not os.path.exists(file_path):
        return render_template(f'source.html', filename='ファイルが見つかりません')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 元のファイル名を復元
        filename_split = filename.split('_')
        filename_head = f"{filename_split[0]}_{filename_split[1]}_{filename_split[2]}_{filename_split[3]}_"
        filename_org = filename.replace(filename_head, '')
    except Exception as e:
        return render_template(f'source.html', filename='ファイルを読み込めません')

    return render_template(f'source.html', source=content, filename=filename_org)


@app.route('/verify/<user_id>/<user_key>', methods=['GET'])
def verify(user_id, user_key):
    verified = False
    
    try:
        verified, user_data = VerifyIdAndKey(user_id, user_key)
    except:
        verified = False

    return "true" if verified else "false"


@app.route('/<task_id>/')
def task_index(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))

    return redirect(url_for('task', task_id=task_id))


@app.route('/<task_id>/timestamp', methods=['GET'])
def get_timestamp(task_id):
    try:
        with open(os.path.join(OUTPUT_DIR, task_id, "timestamp.txt"), "r", encoding='utf-8') as f:
            timestamp = f.read()
    except:
        timestamp = ''

    return timestamp


@app.route('/<task_id>/card.png')
def get_taskcard(task_id):
    return send_from_directory(os.path.join(Task.TASKS_DIR, task_id), "card.png")


@app.route("/<task_id>/task")
def task(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    # タスク情報を読み込む
    task:Task = Task(task_id)

    # Goal表記
    goal_text = GoalText(task.metric, task.goal)

    return render_template(f'tasks/{task_id}/index.html', menu=menuHTML(Page.TASK, task_id, url_from=f"/{task_id}/task"), task_name=TASK[task_id].name, goal=goal_text)


def GoalText(metric:Task.Metric, goal):
    if metric == Task.Metric.Accuracy:
        goal_text = f'正解率 {goal*100:.1f} % 以上'
    elif metric == Task.Metric.MAE:
        goal_text = f'平均絶対誤差 {goal} 以下'
    return goal_text


@app.route("/<task_id>/board")
def board(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    # タスク情報を読み込む
    task:Task = Task(task_id)

    # ユーザ成績を読み込む
    user_stats = GetUserStats(task_id)

    # 辞書をリスト化してソート
    latest_stats_list = []
    for stats in user_stats.values():
        # 各ユーザごとに最新の結果を抽出
        for i in range(len(stats) - 1, -1, -1):
            if task.metric == Task.Metric.Accuracy and stats[i].train[0] < 0:
                continue
            if task.metric == Task.Metric.MAE and stats[i].train < 0:
                continue
            latest_stats_list.append(stats[i])
            break
    sorted_stats_list = sorted(latest_stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table, num_col = CreateTable(sorted_stats_list, task.metric, task.goal)

    # 評価中の表示
    inproc_text = CreateInProcHtml(task_id)

    # Goal表記
    goal_text = GoalText(task.metric, task.goal)

    return render_template('board.html', task_name=TASK[task_id].name, table_board=Markup(html_table), menu=menuHTML(Page.BOARD, task_id, url_from=f"/{task_id}/board"), inproc_text=Markup(inproc_text), num_col=num_col, task_id=task_id, goal=goal_text)


@app.route("/<task_id>/log")
def log(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    # タスク情報を読み込む
    task:Task = Task(task_id)

    # ユーザ成績を読み込む
    user_stats = GetUserStats(task_id)

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table, num_col = CreateTable(sorted_stats_list, task.metric, task.goal)

    # 評価中の表示
    inproc_text = CreateInProcHtml(task_id)

    # Goal表記
    goal_text = GoalText(task.metric, task.goal)

    return render_template('log.html', task_name=TASK[task_id].name, table_log=Markup(html_table), menu=menuHTML(Page.LOG, task_id, url_from=f"/{task_id}/log"), inproc_text=Markup(inproc_text), num_col=num_col, task_id=task_id, goal=goal_text)


@app.route('/<task_id>/upload', methods=['GET', 'POST'])
def upload_file(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    msg = ""

    if request.method == 'POST':
        file = request.files['file']
        if not file:
            msg = "ファイルが選択されていません。"
        elif not allowed_file(file.filename):
            msg = "アップロードできるファイルは.pyのみです。"
        else:
            user_id = request.form['user_id']
            user_key = request.form['user_key']
            
            verified, user_data = VerifyIdAndKey(user_id, user_key)
            if not verified:
                msg = "ユーザ認証に失敗しました。"
            else:
                try:
                    save_dir = os.path.join(UPLOAD_DIR_ROOT, task_id, user_id)

                    # まだディレクトリが存在しなければ作成(Taskのディレクトリがなければそれも生成)
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)

                    if os.path.exists(save_dir):
                        new_filename = secure_filename(file.filename)
                        file.save(os.path.join(save_dir, new_filename))
                        msg = f'{file.filename}がアップロードされました。'

                        # メモを保存
                        if request.form['memo'] != "":
                            with open(os.path.join(save_dir, new_filename + '.txt'), mode='w', encoding='utf-8') as f:
                                f.write(request.form['memo'])
                    else:
                        raise(ValueError("アップロード先のディレクトリが存在しません。"))
                except:
                    msg = "アップロードに失敗しました。"

    return render_template('upload.html', task_id=task_id, task_name=TASK[task_id].name, message=msg, menu=menuHTML(Page.UPLOAD, task_id, url_from=f"/{task_id}/upload"), url_from=f"/{task_id}/upload")
  

@app.route('/<task_id>/admin')
@auth.login_required
def admin(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    # タスク情報を読み込む
    task:Task = Task(task_id)

    # ユーザ成績を読み込む
    user_stats = GetUserStats(task_id)

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table, num_col = CreateTable(sorted_stats_list, task.metric, task.goal, test=True, message=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml(task_id)

    return render_template('log.html', task_id=task_id, task_name=TASK[task_id].name, table_log=Markup(html_table), menu=menuHTML(Page.ADMIN, task_id, url_from=f"/{task_id}/admin"), inproc_text=Markup(inproc_text), num_col=num_col)


if __name__ == "__main__":
    try:
        json_open = open(SETTING_JSON_PATH, 'r', encoding='utf-8')
        SETTING = json.load(json_open)          
    except:
        print(f"settingファイルを開けません: {SETTING_JSON_PATH}")
        exit()

    # タスク一覧を作成
    dir_list = glob.glob(Task.TASKS_DIR + '/**/')
    for dir in dir_list:
        # ディレクトリ名を取得→タスクIDとして使う
        task_id = os.path.basename(os.path.dirname(dir))

        try:
            # タスク情報を取得
            task:Task = Task(task_id)
            print(f"found task: ({task_id}) {task.name}")
            TASK[task_id] = task
        except:
            continue


    # アプリ開始
    app.run(debug=False, host='0.0.0.0', port=5000)
