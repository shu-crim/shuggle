$(document).ready(function() {
    var param = GetQueryString(); // 現在は未使用

    // 自動更新の設定
    var local_storage_check_box_auto_reload = localStorage.getItem(key_check_box_auto_reload);
    if (local_storage_check_box_auto_reload != null && local_storage_check_box_auto_reload == "1") {
        check_box_auto_reload.checked = true;
    }

    // ソート状態の設定
    var sort_index = 1; // デフォルトは提出日時
    var desc = 1; // デフォルトは降順
    var local_storage_index_sorted = localStorage.getItem(key_index_sorted);
    var local_storage_descending = localStorage.getItem(key_descending);
    if (local_storage_index_sorted != null && local_storage_descending != null) {
        sort_index = Number(local_storage_index_sorted)
        if (sort_index < 0 || sort_index >= num_col) {
            sort_index = 1; // デフォルトは提出日時
            desc = 1; // デフォルトは降順
        } else {
            desc = Number(local_storage_descending)
        } 
    }

    $('#fav-table').tablesorter({ 
        sortList: [[sort_index, desc]],
        sortInitialOrder: 'desc'
    });
});

// 表のソートを切り替えるためクリックしたときに状態保存
var key_index_sorted = "index_sorted"
var key_descending = "descending"
$(function() { 
    $("#fav-table")
        .tablesorter()
        .bind("sortEnd",function() {
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

            localStorage.setItem(key_index_sorted, index_sorted);
            localStorage.setItem(key_descending, descending ? "1" : "0");
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
                        location.reload();
                    }
                }
            }
        }
        request.send("");
    }, 1000);
});


// 自動更新をONにしたときには一度強制リロード
var key_check_box_auto_reload = "check_box_auto_reload"
check_box_auto_reload.addEventListener('click', checkBoxClick);
function checkBoxClick() {
    if (check_box_auto_reload.checked) {
        localStorage.setItem(key_check_box_auto_reload, "1");
        location.reload();
    } else {
        localStorage.setItem(key_check_box_auto_reload, "0");
    }
}


// 手動のリロードボタン
let button_reload = document.getElementById('ButtonReload');
button_reload.addEventListener('click', butotnReloadClick);
function butotnReloadClick() {
    location.reload();
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