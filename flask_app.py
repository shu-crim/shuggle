from flask import Flask, render_template, request, redirect, url_for, make_response, Markup
from flask_httpauth import HTTPBasicAuth, HTTPDigestAuth
from werkzeug.utils import secure_filename
import json

import os
import glob
import datetime
from enum import Enum


USER_RESULT_DIR = r"./output/user"
UPLOAD_DIR_ROOT = r"./upload_dir"
TIMESTAMP_FILE_PATH = r"./output/timestamp.txt"
ALLOWED_EXTENSIONS = set(['py'])
TASK_NAME = "タスク"


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
    TASK = 1,
    BOARD = 2,
    LOG = 3,
    UPLOAD = 4,
    ADMIN = 9


#Flaskオブジェクトの生成
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 #ファイルサイズ制限 2MB
app.config['SECRET_KEY'] = 'secret key here'
auth = HTTPDigestAuth()
auth_users = {
    "root": "password",
}


def GetUserStats() -> {}:
    def TransIntIntFloat(true_false_accuracy : list):
        result = [0, 0, 0.0]
        try:
            result[0] = int(true_false_accuracy[0])
            result[1] = int(true_false_accuracy[1])
            result[2] = float(true_false_accuracy[2])
        except:
            return [0, 0, 0.0]
        return result

    file_paths = glob.glob(os.path.join(USER_RESULT_DIR, "*.csv"))
    stats = {}
    for file_path in file_paths:
        user_name = os.path.splitext(os.path.basename(file_path))[0]
        stats[user_name] = []
        
        with open(file_path, "r", encoding='shift_jis') as csv_file:    
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


def menuHTML(page, task_name):
    html = """
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
            <div class="container-fluid">
                <a class="navbar-brand">Shuggle</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarSupportedContent" aria-controls="navbarSupportedContent" aria-expanded="false" aria-label="Toggle navigation">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarSupportedContent">
                    <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                        <li class="nav-item">
                            <a class="nav-link{0} href="/task">{1}</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{2} href="/board">評価結果</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{3} href="/log">履歴</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{4} href="/upload">提出</a>
                        </li>
                        {5}
                    </ul>
                </div>
            </div>
        </nav>

    """.format(
        " active\" aria-current=\"page\"" if page == Page.TASK else "\"",
        task_name,
        " active\" aria-current=\"page\"" if page == Page.BOARD else "\"",
        " active\" aria-current=\"page\"" if page == Page.LOG else "\"",
        " active\" aria-current=\"page\"" if page == Page.UPLOAD else "\"",
        """
        <li class="nav-item">
            <a class="nav-link active href="/admin">管理者</a>
        </li>
        """ if page == Page.ADMIN else ""
    )

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
    html_table = ""
    html_table += "<table class=\"table table-dark\" id=\"fav-table\">"
    html_table += "<thead><tr><th>参加者</th><th>提出日時</th><th>train(配布)正解率</th><th>valid正解率</th>"
    if test:
        html_table += "<th>test正解率</th>"
    if memo:
        html_table += "<th>メモ</th>"
    if message:
        html_table += "<th>メッセージ</th>"
    html_table += "</tr></thead>"
    html_table += "<tbody>"

    for stats in stats_list:
        html_table += CreateTableRow(stats, test=test, message=message, memo=memo)

    html_table += "</tbody>"
    html_table += "</table>"

    return html_table


def GetUserNames():
    user_name_list = []
    dir_list = glob.glob(os.path.join(UPLOAD_DIR_ROOT, "**/"))
    for dir in dir_list:
        # ディレクトリ名を取得→ユーザ名として使う
        user_name = os.path.basename(os.path.dirname(dir))
        user_name_list.append(user_name)

    return user_name_list


def CreateInProcHtml():
    inproc_text = ''
    user_name_list = GetUserNames()
    for user_name in user_name_list:
        if os.path.exists(os.path.join(USER_RESULT_DIR, f"{user_name}_inproc")):
            inproc_text += f"{user_name} さんの評価を実行中です。<br>"

    return inproc_text + '<br>'
    

@auth.get_password
def get_pw(username):
    if username in auth_users:
        return auth_users.get(username)
    return None


@app.route('/')
def index():
    # /boardにリダイレクト
    return redirect(url_for('board'))


@app.route('/timestamp', methods=['GET'])
def get_timestamp():
    try:
        with open(TIMESTAMP_FILE_PATH, "r") as f:
            timestamp = f.read()
    except:
        timestamp = ''

    return timestamp


@app.route("/task")
def task():

    return render_template('task.html', menu=menuHTML(Page.TASK, TASK_NAME), task_name=TASK_NAME)


@app.route("/board")
def board():
    user_stats = GetUserStats()

    # 辞書をリスト化してソート
    latest_stats_list = []
    for user_name, stats in user_stats.items():
        latest_stats_list.append(stats[-1])
    sorted_stats_list = sorted(latest_stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table = CreateTable(sorted_stats_list, memo=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml()

    return render_template('board.html', table_board=Markup(html_table), menu=menuHTML(Page.BOARD, TASK_NAME), task_name=TASK_NAME, inproc_text=Markup(inproc_text))


@app.route("/log")
def log():
    user_stats = GetUserStats()

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table = CreateTable(sorted_stats_list, message=True, memo=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml()

    return render_template('log.html', task_name=TASK_NAME, table_log=Markup(html_table), menu=menuHTML(Page.LOG, TASK_NAME), inproc_text=Markup(inproc_text))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    msg = ""
    cookie_write = False

    if request.method == 'POST':
        file = request.files['file']
        user = request.form['user']
        cookie_write = True
        if not file:
            msg = "ファイルが選択されていません。"
        elif not allowed_file(file.filename):
            msg = "アップロードできるファイルは.pyのみです。"
        else:
            try:
                user = request.form['user']
                save_dir = os.path.join(UPLOAD_DIR_ROOT, user)
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


    if not cookie_write:
        # 既存のクッキーから過去の選択を読み出し
        user_info = request.cookies.get('user_info')
        if user_info is not None:
            user_info = json.loads(user_info)
            user = user_info['name']
        else:
            user = 'anonymous'

    # ディレクトリ名からユーザ名のlistを作成
    user_name_list = GetUserNames()

    response = make_response(render_template('upload.html', task_name=TASK_NAME, message=msg, username=user_name_list, selected_user=user, menu=menuHTML(Page.UPLOAD, TASK_NAME)))

    # クッキー書き込み
    if cookie_write:
        expires = int(datetime.datetime.now().timestamp()) + 10 * 24 * 3600
        user_info = {'name': user} 
        response.set_cookie('user_info', value=json.dumps(user_info), expires=expires)

    return response
  

@app.route('/admin')
@auth.login_required
def admin():
    user_stats = GetUserStats()

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    # 表を作成
    html_table = CreateTable(sorted_stats_list, test=True, message=True)

    # 評価中の表示
    inproc_text = CreateInProcHtml()

    return render_template('log.html', task_name=TASK_NAME, table_log=Markup(html_table), menu=menuHTML(Page.ADMIN, TASK_NAME), inproc_text=Markup(inproc_text))


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=5000)