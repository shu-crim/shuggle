$(document).ready(function() {
    var param = GetQueryString();

    // 自動更新の設定
    if (param != null && param["autoreload"] != undefined) {
        if (param["autoreload"] == "1") {
            check_box_auto_reload.checked = true;
        }
    }

    // ソート状態の設定
    var sort_index = 1; // デフォルトは提出日時
    var desc = 1; // デフォルトは降順
    if (param != null && param["sortindex"] != undefined && param["desc"] != undefined) {
        sort_index = param["sortindex"];
        desc = param["desc"];
    }

    $('#fav-table').tablesorter({ 
        sortList: [[sort_index, desc]],
        sortInitialOrder: 'desc'
    });
});

var check_box_auto_reload = document.getElementById("CheckBoxAutoReload")
var current_timestamp = ""
window.addEventListener('DOMContentLoaded', function(){
    // 1秒ごとに実行
    setInterval(() => {
        // 自動更新がONかチェック
        if (!check_box_auto_reload.checked && current_timestamp != "") {
            return;
        }

        // タイムスタンプを確認して更新があればリロード
        var request = new XMLHttpRequest()
        request.open("GET", "/timestamp", true);
        request.onreadystatechange = function() {
            if (request.readyState == 4 && request.status == 200) {
                //受信完了時の処理
                var timestamp = document.createTextNode(decodeURI(request.responseText));

                if (current_timestamp == "") {
                    current_timestamp = timestamp;
                } else {
                    if (current_timestamp.data != timestamp.data) {
                        reload();
                    }
                }
            }
        }
        request.send("");
    }, 1000);
});


// 自動更新をONにしたときには一度強制リロード
check_box_auto_reload.addEventListener('click', checkBoxClick);
function checkBoxClick() {
    if (check_box_auto_reload.checked) {
        reload();
    }
}


// 手動のリロードボタン
let button_reload = document.getElementById('ButtonReload');
button_reload.addEventListener('click', butotnReloadClick);
function butotnReloadClick() {
    reload();
}


function reload() {
    // 現在のソート状態を取得
    var index_sorted = -1;
    var descending = true
    for (let i = 0; i < num_col; i++) {
        var id = "th-" + i
        var class_name = document.getElementById(id).className
        if (class_name.includes('tablesorter-headerAsc')) {
            index_sorted = i;
            descending = false;
        } else if(class_name.includes('tablesorter-headerDesc')) {
            index_sorted = i;
            descending = true;
        }
    }

    // パラメータを付与してリロード
    let url = window.location.href;
    url = url.replace(location.search , '');

    // 自動更新
    url += "?autoreload=" + (check_box_auto_reload.checked ? "1" : "0");

    // ソート状態
    if (index_sorted >= 0){
        url += "&sortindex=" + index_sorted + "&desc=" + (descending ? "1" : "0");
    }

    window.location.href = url
}

// URLからパラメータを取得
function GetQueryString() {
    if (location.search.length > 1) {
        var query = document.location.search.substring(1);
        var parameters = query.split('&');

        var result = new Object();
        for (var i = 0; i < parameters.length; i++) {
            var element = parameters[i].split('=');

            var paramName = decodeURIComponent(element[0]);
            var paramValue = decodeURIComponent(element[1]);

            result[paramName] = decodeURIComponent(paramValue);
        }
        return result;
    }
    return null;
}