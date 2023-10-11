from flask import Flask, render_template, request, redirect, url_for, make_response, Markup, send_from_directory
from flask_httpauth import HTTPBasicAuth, HTTPDigestAuth
from werkzeug.utils import secure_filename
import json

import os
import glob
import datetime
from enum import Enum


INPUT_DATA_DIR = r"./input_data"
OUTPUT_DIR = r"./output"
UPLOAD_DIR_ROOT = r"./upload_dir"
ALLOWED_EXTENSIONS = set(['py'])
TASK_NAME = {}
TASK_ID_LIST = []


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

    file_paths = glob.glob(os.path.join(OUTPUT_DIR, task_id, "user", "*.csv"))
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


def menuHTML(page, task_id):
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
                    </ul>
                </div>
            </div>
        </nav>

    """.format(
        TASK_NAME[task_id],
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


def GetUserNames(task_id):
    user_name_list = []
    dir_list = glob.glob(os.path.join(UPLOAD_DIR_ROOT, task_id, "**/"))
    for dir in dir_list:
        # ディレクトリ名を取得→ユーザ名として使う
        user_name = os.path.basename(os.path.dirname(dir))
        user_name_list.append(user_name)

    return user_name_list


def CreateInProcHtml(task_id):
    inproc_text = ''
    user_name_list = GetUserNames(task_id)
    for user_name in user_name_list:
        if os.path.exists(os.path.join(OUTPUT_DIR, task_id, "user", f"{user_name}_inproc")):
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


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/img'), 'favicon.ico', )


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
    if not task_id in TASK_ID_LIST:
        return # TODO:タスクが存在しないときのページへリダイレクト

    return render_template(f'task/{task_id}.html', menu=menuHTML(Page.TASK, task_id), task_name=TASK_NAME[task_id])


@app.route("/<task_id>/board")
def board(task_id):
    if not task_id in TASK_ID_LIST:
        return # TODO:タスクが存在しないときのページへリダイレクト
    
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

    return render_template('board.html', task_name=TASK_NAME[task_id], table_board=Markup(html_table), menu=menuHTML(Page.BOARD, task_id), inproc_text=Markup(inproc_text), num_col=num_col, task_id=task_id)


@app.route("/<task_id>/log")
def log(task_id):
    if not task_id in TASK_ID_LIST:
        return # TODO:タスクが存在しないときのページへリダイレクト
    
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

    return render_template('log.html', task_name=TASK_NAME[task_id], table_log=Markup(html_table), menu=menuHTML(Page.LOG, task_id), inproc_text=Markup(inproc_text), num_col=num_col, task_id=task_id)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/<task_id>/upload', methods=['GET', 'POST'])
def upload_file(task_id):
    if not task_id in TASK_ID_LIST:
        return # TODO:タスクが存在しないときのページへリダイレクト
    
    msg = ""

    if request.method == 'POST':
        file = request.files['file']
        user = request.form['user']
        if not file:
            msg = "ファイルが選択されていません。"
        elif not allowed_file(file.filename):
            msg = "アップロードできるファイルは.pyのみです。"
        else:
            try:
                user = request.form['user']
                save_dir = os.path.join(UPLOAD_DIR_ROOT, task_id, user)
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

    # ディレクトリ名からユーザ名のlistを作成
    user_name_list = GetUserNames(task_id)

    return render_template('upload.html', task_name=TASK_NAME[task_id], message=msg, username=user_name_list, menu=menuHTML(Page.UPLOAD, task_id))
  

@app.route('/<task_id>/admin')
@auth.login_required
def admin(task_id):
    if not task_id in TASK_ID_LIST:
        return # TODO:タスクが存在しないときのページへリダイレクト
    
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

    return render_template('log.html', task_id=task_id, task_name=TASK_NAME[task_id], table_log=Markup(html_table), menu=menuHTML(Page.ADMIN, task_id), inproc_text=Markup(inproc_text), num_col=num_col)


if __name__ == "__main__":
    # タスク一覧を作成
    dir_list = glob.glob(INPUT_DATA_DIR + '/**/')
    for dir in dir_list:
        # ディレクトリ名を取得→タスクIDとして使う
        task_id = os.path.basename(os.path.dirname(dir))

        try:
            # タスク名を取得
            with open(os.path.join(dir, "task_name.txt"), "r", encoding='shift_jis') as f:
                task_name = f.readline()

            print(f"found task: ({task_id}) {task_name}")
            TASK_ID_LIST.append(task_id)
            TASK_NAME[task_id] = task_name
        except:
            continue


    # アプリ開始
    app.run(debug=False, host='0.0.0.0', port=5000)