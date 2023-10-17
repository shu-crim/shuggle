from flask import Flask, render_template, request, redirect, url_for, make_response, Markup, send_from_directory
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


INPUT_DATA_DIR = r"./input_data"
OUTPUT_DIR = r"./output"
UPLOAD_DIR_ROOT = r"./upload_dir"
ALLOWED_EXTENSIONS = set(['py'])
TASK = {}
USER_CSV_PATH = r"./data/users.csv"
HASH_METHOD = "pbkdf2:sha256:260000"


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


class Task():
    name : str
    explanation : str
    start_date : datetime.datetime
    end_date : datetime.datetime

    def __init__(self, name, explanation, start_date, end_date) -> None:
        self.name = name
        self.explanation = explanation
        self.start_date = start_date
        self.end_date = end_date


class Stats():
    username : str
    datetime : datetime
    filename : str = ""
    train : list = [0, 0, 0.0]
    valid : list = [0, 0, 0.0]
    test : list = [0, 0, 0.0]
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
        with open(path) as f:
            f.readline() # ヘッダを読み飛ばす
            while True:
                line = f.readline()
                if not line:
                    break
                email, id, name, key, pass_hash = line.rstrip().split(',')
                users[id] = UserData(id, email, pass_hash, name, key)
    except:
        return None

    return users


def WriteUsersCsv(path:str, users:dict, must_backup:bool=True) -> bool:
    # バックアップをとる
    try:
        shutil.copy2(path, os.path.join(os.path.dirname(path), "backup", datetime.datetime.now().strftime('users_%Y%m%d_%H%M%S_%f.csv')))
    except:
        if must_backup:
            return False
    
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
            return [0, 0, 0.0]
        return result

    # ユーザ情報を読み込む
    users = ReadUsersCsv(USER_CSV_PATH)

    file_paths = glob.glob(os.path.join(OUTPUT_DIR, task_id, "user", "*.csv"))
    stats = {}
    for file_path in file_paths:
        user_id = os.path.splitext(os.path.basename(file_path))[0]
        if not user_id in users:
            continue
        user_name = users[user_id].name
        stats[user_name] = []
        
        with open(file_path, "r", encoding='utf-8') as csv_file:
            line = csv_file.readline() # ヘッダ読み飛ばし
            while True:
                line = csv_file.readline()
                if not line:
                    break

                raw = line.rstrip(os.linesep).split(",")
                if len(raw) < 13:
                    continue

                try:
                    dt = datetime.datetime.strptime(raw[0] + " " + raw[1], "%Y/%m/%d %H:%M:%S")
                    filename = raw[2]
                    train = TransIntIntFloat(raw[3:6])
                    valid = TransIntIntFloat(raw[6:9])
                    test = TransIntIntFloat(raw[9:12])
                    message = raw[12]
                    memo = raw[13] if len(raw) >= 14 else ""

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
                    stats[user_name].append(stats_read)
                except Exception as e:
                    print(e)

        # ひとつも読めなかった場合はキーを削除
        if len(stats[user_name]) == 0:
            stats.pop(user_name)

    return stats


def menuHTML(page, task_id=""):
    html = """
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
            <div class="container-fluid">
                <a class="navbar-brand" href="/"><span style="color:#00a497">S</span>huggle</a>
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

    html += """
                    </ul>
                    <ul class="navbar-nav ml-auto mb-2 mb-lg-0">
                        <li class="nav-item">
                            <a id="login-user-name" class="nav-link active" aria-current="page" href="/user/info"></a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    """

    return Markup(html)


def CreateTableRow(stats, test=False, message=False, memo=False):
    html_user = ""
    html_user += f'<tr>'
    html_user += f'<td>{stats.username}</td>'
    html_user += f'<td>{stats.datetime}</td>'
    html_user += f'<td>{stats.train[2] * 100:.2f} %</td>' if stats.train[0] + stats.train[1] > 0 else '<td>0.00 %</td>'
    html_user += f'<td>{stats.valid[2] * 100:.2f} %</td>' if stats.valid[0] + stats.valid[1] > 0 else '<td>0.00 %</td>'
    if test:
        html_user += f'<td>{stats.test[2] * 100:.2f} %</td>' if stats.test[0] + stats.test[1] > 0 else '<td>0.00 %</td>'
    if memo:
        html_user += f'<td>{stats.memo}</td>'
    if message:
        html_user += f'<td>{stats.message}</td>'
    html_user += f'</tr>'
    return html_user


def CreateTable(stats_list, test=False, message=False, memo=False):
    num_col = 0
    html_table = ""
    html_table += "<table class=\"table table-dark\" id=\"fav-table\">"
    html_table += "<thead><tr>"
    html_table += f"<th id=\"th-{num_col}\">参加者</th>"
    num_col += 1
    html_table += f"<th id=\"th-{num_col}\">提出日時</th>"
    num_col += 1
    html_table += f"<th id=\"th-{num_col}\">train(配布)正解率</th>"
    num_col += 1
    html_table += f"<th id=\"th-{num_col}\">valid正解率</th>"
    num_col += 1
    if test:
        html_table += f"<th id=\"th-{num_col}\">test正解率</th>"
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
        html_table += CreateTableRow(stats, test=test, message=message, memo=memo)

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


def VerifyEmailAndPassword(email, password):
    # ユーザ情報を読み込む
    users = ReadUsersCsv(USER_CSV_PATH)
    
    # 認証を行う
    verified = False
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
    task_list_open = []
    task_list_closed = []
    for key, value in TASK.items():
        if value.start_date <= today and value.end_date > today:
            task_list_open.append(
                {
                    'id': key,
                    'name': value.name,
                    'explanation': value.explanation
                }
            )
        if value.end_date <= today:
            task_list_closed.append(
                {
                    'id': key,
                    'name': value.name,
                    'explanation': value.explanation
                }
            )
    
    return render_template(f'index.html', task_list_open=task_list_open, task_list_closed=task_list_closed, menu=menuHTML(Page.HOME))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'), 'favicon.ico', )


@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'GET':
        return render_template(f'join.html', message="")
    
    elif request.method == 'POST':
        try:
            email = request.form['inputEmail']
            password = request.form['inputPassword']
            password_verify = request.form['inputPasswordVerify']
            next_url = request.form['nextUrl']
        except:
            return render_template(f'join.html', message="入力データを受け取れませんでした。")
        
        # 2つのパスワード入力の一致チェック
        if password != password_verify:
            return render_template(f'join.html', message="再入力したパスワードが一致していません。")
        
        # ユーザ情報を読み込む
        users = ReadUsersCsv(USER_CSV_PATH)

        # email重複チェック
        duplicate = False
        for user_id, user_data in users.items():
            if email == user_data.email:
                duplicate = True
                break
        if duplicate:
            return render_template(f'join.html', message="そのEmail addressは既に登録されています。")
        
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
            return render_template(f'join.html', message="IDを発行できませんでした。")
        
        # パスワードをハッシュ化
        pass_hash = generate_password_hash(password, salt_length=21)
        
        # 本人確認用のキーを作成
        user_key = str(uuid.uuid4()).split('-')[0]

        # ユーザ登録
        name = email.split('@')[0]
        success = AddUsersCsv(USER_CSV_PATH, user_id, email, name, pass_hash, user_key)

        if not success:
            return render_template(f'join.html', message="ユーザ情報を登録できませんでした。")

        return render_template(f'user.html', user_email=email, user_id=user_id, user_key=user_key, user_name=name, next_url=next_url, login="true", update_user_data="true")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template(f'login.html', message="")
    
    elif request.method == 'POST':
        try:
            email = request.form['inputEmail']
            password = request.form['inputPassword']
            next_url = request.form['nextUrl']
        except:
            return render_template(f'login.html', message="入力データを受け取れませんでした。")
        
        # emailとパスワードで照合
        verified, user_data = VerifyEmailAndPassword(email, password)
        if not verified:
            return render_template(f'login.html', message="Email addressかPasswordが誤っています。")

        # 認証OKなので本人確認用のキーを作成して渡す
        user_key = str(uuid.uuid4()).split('-')[0]

        # キーを保存
        UpdateUsersCsv(USER_CSV_PATH, user_data.id, 'key', user_key)

        return render_template(f'user.html', user_email=email, user_id=user_data.id, user_key=user_key, user_name=user_data.name, next_url=next_url, login="true", update_user_data="true")


@app.route('/user/info', methods=['GET', 'POST'])
def user():
    if request.method == 'GET':
        return render_template(f'user.html', login="false")

    elif request.method == 'POST':
        try:
            new_name = request.form['newName']
            user_id = request.form['userID']
            user_key = request.form['userKey']
            verified = VerifyIdAndKey(user_id, user_key)
            if verified:
                # 名前を変更
                success = UpdateUsersCsv(USER_CSV_PATH, user_id, 'name', new_name)
                if not success:
                    raise(ValueError())
        except:
            return render_template(f'user.html')
        
        return render_template(f'user.html', user_name=new_name, update_user_data="true")

@app.route('/verify/<user_id>/<user_key>', methods=['GET'])
def verify(user_id, user_key):
    verified = False
    
    try:
        verified = VerifyIdAndKey(user_id, user_key)
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
        with open(os.path.join(OUTPUT_DIR, task_id, "timestamp.txt"), "r") as f:
            timestamp = f.read()
    except:
        timestamp = ''

    return timestamp


@app.route("/<task_id>/task")
def task(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))

    return render_template(f'task/{task_id}.html', menu=menuHTML(Page.TASK, task_id), task_name=TASK[task_id].name)


@app.route("/<task_id>/board")
def board(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    user_stats = GetUserStats(task_id)

    # 辞書をリスト化してソート
    latest_stats_list = []
    for user_name, stats in user_stats.items():
        latest_stats_list.append(stats[-1])
    sorted_stats_list = sorted(latest_stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table, num_col = CreateTable(sorted_stats_list, memo=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml(task_id)

    return render_template('board.html', task_name=TASK[task_id].name, table_board=Markup(html_table), menu=menuHTML(Page.BOARD, task_id), inproc_text=Markup(inproc_text), num_col=num_col, task_id=task_id)


@app.route("/<task_id>/log")
def log(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    user_stats = GetUserStats(task_id)

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table, num_col = CreateTable(sorted_stats_list, message=True, memo=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml(task_id)

    return render_template('log.html', task_name=TASK[task_id].name, table_log=Markup(html_table), menu=menuHTML(Page.LOG, task_id), inproc_text=Markup(inproc_text), num_col=num_col, task_id=task_id)


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
            
            verified = VerifyIdAndKey(user_id, user_key)
            if not verified:
                msg = "ユーザ認証に失敗しました。"
            else:
                try:
                    save_dir = os.path.join(UPLOAD_DIR_ROOT, task_id, user_id)

                    # まだディレクトリが存在しなければ作成
                    if not os.path.exists(save_dir):
                        os.mkdir(save_dir)

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

    return render_template('upload.html', task_id=task_id, task_name=TASK[task_id].name, message=msg, menu=menuHTML(Page.UPLOAD, task_id))
  

@app.route('/<task_id>/admin')
@auth.login_required
def admin(task_id):
    if not task_id in TASK:
        return redirect(url_for('index'))
    
    user_stats = GetUserStats(task_id)

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table, num_col = CreateTable(sorted_stats_list, test=True, message=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml(task_id)

    return render_template('log.html', task_id=task_id, task_name=TASK[task_id].name, table_log=Markup(html_table), menu=menuHTML(Page.ADMIN, task_id), inproc_text=Markup(inproc_text), num_col=num_col)


if __name__ == "__main__":
    # タスク一覧を作成
    dir_list = glob.glob(INPUT_DATA_DIR + '/**/')
    for dir in dir_list:
        # ディレクトリ名を取得→タスクIDとして使う
        task_id = os.path.basename(os.path.dirname(dir))

        try:
            # タスク名を取得
            with open(os.path.join(dir, "task_name.txt"), "r", encoding='utf-8') as f:
                task_name = f.readline().rstrip()
                task_explanation = f.readline().rstrip()
                date = f.readline().rstrip()
                start_date = datetime.datetime.strptime(date, '%Y-%m-%d')
                date = f.readline().rstrip()
                end_date = datetime.datetime.strptime(date, '%Y-%m-%d')

            print(f"found task: ({task_id}) {task_name} {task_explanation}")
            TASK[task_id] = Task(task_name, task_explanation, start_date, end_date)
        except:
            continue


    # アプリ開始
    app.run(debug=False, host='0.0.0.0', port=5000)