
// ユーザ認証を行い、認証されたらメニュー右端の「ログイン」リンクの名前をユーザ名にする
$(document).ready(function() {
    var id_user_name = document.getElementById("login-user-name");

    // ユーザ情報が保存されていたら取得
    var user_id = localStorage.getItem("user_id");
    var user_key = localStorage.getItem("user_key");
    var user_name = localStorage.getItem("user_name");

    // ユーザ情報がない
    if (user_id == null || user_name == null || user_key == null){
        id_user_name.textContent = "ログイン";
        return;
    }

    // ユーザ情報を照合
    var request = new XMLHttpRequest()
    request.open("GET", "/verify/" + user_id + "/" + user_key, true);
    request.onreadystatechange = function() {
        if (request.readyState == 4 && request.status == 200) {
            //受信完了時の処理
            var verify = document.createTextNode(decodeURI(request.responseText));

            if (verify.data == "true") {
                // 照合に成功したらユーザ名を表示
                if (id_user_name != null) {
                    id_user_name.textContent = user_name + " さんのユーザページ";
                }
            } else {
                id_user_name.textContent = "ログイン";
            }
        }
    }
    request.send("");
});
