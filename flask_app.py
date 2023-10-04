from flask import Flask, render_template, request, redirect, url_for, make_response, Markup
from werkzeug.utils import secure_filename
import json

import os
import glob
import datetime
from enum import Enum

USER_RESULT_DIR = r"./output/user"
UPLOAD_DIR_ROOT = r"./upload_dir"
ALLOWED_EXTENSIONS = set(['py'])

class Stats():
    username : str
    datetime : datetime
    filename : str
    train : list
    valid : list
    test : list
    message : str


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

                try:
                    raw = line.rstrip(os.linesep).split(",")
                    stats_read = Stats()

                    dt = datetime.datetime.strptime(raw[0] + " " + raw[1], "%Y/%m/%d %H:%M:%S")
                    filename = raw[2]
                    train = TransIntIntFloat(raw[3:6])
                    valid = TransIntIntFloat(raw[6:9])
                    test = TransIntIntFloat(raw[9:12])
                    message = raw[12]

                    # すべて読めたら保持
                    stats_read.username = user_name
                    stats_read.datetime = dt
                    stats_read.filename = filename
                    stats_read.train = train
                    stats_read.valid = valid
                    stats_read.test = test
                    stats_read.message = message
                    stats[user_name].append(stats_read)
                except Exception as e:
                    print(e)
    return stats

class Page(Enum):
    BOARD = 1,
    LOG = 2,
    UPLOAD = 3

def menuHTML(page):
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
                            <a class="nav-link{0} href="/board">結果一覧</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{1} href="/log">履歴</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link{2} href="/upload">提出</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>

    """.format(
        " active\" aria-current=\"page\"" if page == Page.BOARD else "\"",
        " active\" aria-current=\"page\"" if page == Page.LOG else "\"",
        " active\" aria-current=\"page\"" if page == Page.UPLOAD else "\""
    )

    return Markup(html)

#Flaskオブジェクトの生成
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 #ファイルサイズ制限 2MB

@app.route('/')
def index():
    # /boardにリダイレクト
    return redirect(url_for('board'))


@app.route("/board")
def board():
    user_stats = GetUserStats()

    # 辞書をリスト化してソート
    latest_stats_list = []
    for user_name, stats in user_stats.items():
        latest_stats_list.append(stats[-1])
    sorted_stats_list = sorted(latest_stats_list, key=lambda x: x.datetime, reverse=True)

    html_table = ""
    html_table += "<table class=\"table table-dark\">"
    html_table += "<thead><tr><th>参加者</th><th>最終提出日時</th><th>train(配布)正解率</th><th>valid正解率</th><th>test正解率</th></tr></thead>"
    html_table += "<tbody>"

    for stats in sorted_stats_list:
        try:
            html_user = ""
            html_user += f'<tr>'
            html_user += f'<td>{stats.username}</td>'
            html_user += f'<td>{stats.datetime}</td>'
            html_user += f'<td>{stats.train[2] * 100  if (stats.train[0] + stats.train[1] > 0) else "-":.2f} %</td>'
            html_user += f'<td>{stats.valid[2] * 100 if (stats.valid[0] + stats.valid[1] > 0) else "-":.2f} %</td>'
            html_user += f'<td>{stats.test[2] * 100 if (stats.test[0] + stats.test[1] > 0) else "-":.2f} %</td>'
            html_user += f'</tr>'

            html_table += html_user
        except:
            continue

    html_table += "</tbody>"
    html_table += "</table>"

    return render_template('board.html', table_board=Markup(html_table), menu=menuHTML(Page.BOARD))


@app.route("/log")
def log():
    user_stats = GetUserStats()

    # 辞書をリスト化してソート
    stats_list = []
    for stats in user_stats.values():
        for item in stats:
            stats_list.append(item)
    sorted_stats_list = sorted(stats_list, key=lambda x: x.datetime, reverse=True)

    html_table = ""
    html_table += "<table class=\"table table-dark\">"
    html_table += "<thead><tr><th>参加者</th><th>登録日時</th><th>train(配布)正解率</th><th>valid正解率</th><th>test正解率</th><th>メッセージ</th></tr></thead>"
    html_table += "<tbody>"

    for stats in sorted_stats_list:
        html_user = ""
        try:
            html_user += f'<tr>'
            html_user += f'<td>{stats.username}</td>'
            html_user += f'<td>{stats.datetime}</td>'
            html_user += f'<td>{stats.train[2] * 100:.2f} %</td>' if stats.train[0] + stats.train[1] > 0 else '<td>-</td>'
            html_user += f'<td>{stats.valid[2] * 100:.2f} %</td>' if stats.valid[0] + stats.valid[1] > 0 else '<td>-</td>'
            html_user += f'<td>{stats.test[2] * 100:.2f} %</td>' if stats.test[0] + stats.test[1] > 0 else '<td>-</td>'
            html_user += f'<td>{stats.message}</td>'
            html_user += f'</tr>'
        except:
            continue

        html_table += html_user
        
    html_table += "</tbody>"
    html_table += "</table>"

    return render_template('log.html', table_log=Markup(html_table), menu=menuHTML(Page.LOG))


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
                    file.save(os.path.join(save_dir, secure_filename(file.filename)))
                    msg = f'{file.filename}がアップロードされました。'
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
    user_name_list = []
    dir_list = glob.glob(os.path.join(UPLOAD_DIR_ROOT, "**/"))
    for dir in dir_list:
        # ディレクトリ名を取得→ユーザ名として使う
        user_name = os.path.basename(os.path.dirname(dir))
        user_name_list.append(user_name)

    response = make_response(render_template('upload.html', message=msg, username=user_name_list, selected_user=user, menu=menuHTML(Page.UPLOAD)))

    # クッキー書き込み
    if cookie_write:
        expires = int(datetime.datetime.now().timestamp()) + 10 * 24 * 3600
        user_info = {'name': user} 
        response.set_cookie('user_info', value=json.dumps(user_info), expires=expires)

    return response
  

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=5000)