$(document).ready(function() {
    var param = GetQueryString();
    console.log(param)
    var sort_index = 1; // デフォルトは提出日時
    var desc = 1; // デフォルトは降順
    if (param != null && param["sortindex"] != undefined && param["desc"] != undefined) {
        sort_index = param["sortindex"];
        desc = param["desc"];
        console.log("sort_index: " + sort_index)
        console.log("desc: " + desc)
    }

    $('#fav-table').tablesorter({ 
        sortList: [[sort_index, desc]],
        sortInitialOrder: 'desc'
    });
});

var current_timestamp = ""
window.addEventListener('DOMContentLoaded', function(){
    // 1秒ごとに実行
    setInterval(() => {
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
                        console.log("reload()");
                        reload();
                    }
                }
            }
        }
        request.send("");
    }, 1000);
});

function reload() {
    // 現在のソート状態を取得
    var index_sorted = -1;
    var ascending = true
    for (let i = 0; i < num_col; i++) {
        var id = "th-" + i
        var class_name = document.getElementById(id).className
        if (class_name.includes('tablesorter-headerAsc')) {
            index_sorted = i;
            ascending = true;
        } else if(class_name.includes('tablesorter-headerDesc')) {
            index_sorted = i;
            ascending = false;
        }
    }

    // パラメータを付与してリロード
    let url = window.location.href;
    url = url.replace(location.search , '');
    if (index_sorted >= 0){
        url += "?sortindex=" + index_sorted
        if (ascending) {
            url += "&desc=0"
        } else {
            url += "&desc=1"
        }                    
    }                
    window.location.href = url
}

// URLからパラメータを取得
function GetQueryString() {
    console.log("GetQueryString()")
    console.log("document.location.search.length: " + location.search.length)
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