import json

# 1. 讀取三鶯線完整 JSON 檔
with open("sanying_timetable.json", "r", encoding="utf-8-sig") as f:
  full_data = json.load(f)

# 2. 將 Python 物件轉成 JSON 字串
json_str = json.dumps(full_data, ensure_ascii=False)

# 3. 使用一般字串組合網頁內容
html_content = (
    """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>新北捷運三鶯線 - 車站時刻表查詢</title>
  <style>
    * { box-sizing: border-box; }
    body { 
      margin: 0; 
      background: #121212; 
      color: #e0e0e0; 
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
      display: flex; 
      justify-content: center; 
      padding: 12px; 
      width: 100%;   
    }
    .calculator { 
      background: #1e1e1e; 
      padding: 20px; 
      border-radius: 16px; 
      width: 100%;       
      max-width: 520px; 
      border: 1px solid #333; 
      box-shadow: 0 12px 30px rgba(0,0,0,0.45); 
      overflow: hidden;  
    }
    h1 { font-size: 1.25rem; color: #39C0E1; text-align: center; margin: 0 0 15px; }
    .label-hint { font-size: 0.8rem; color: #888; margin-bottom: 10px; }
    .input-group { margin-bottom: 15px; }
    label { display: block; font-size: 0.82rem; margin-bottom: 6px; color: #aaa; }
    select, input { 
      width: 100%; 
      padding: 11px; 
      background: #252525; 
      border: 1px solid #444; 
      border-radius: 8px; 
      color: #fff; 
      outline: none; 
      font-size: 0.95rem;
    }
    select:focus, input:focus { border-color: #39C0E1; }
    .calc-btn { 
      width: 100%;
      background: #39C0E1; 
      color: #121212; 
      border: none; 
      padding: 12px; 
      border-radius: 8px; 
      font-weight: bold; 
      cursor: pointer; 
      font-size: 0.95rem;
      transition: background 0.2s;
    }
    .calc-btn:hover { background: #2aa8c4; }
    hr { border: 0; border-top: 1px solid #333; margin: 20px 0; }
    .result-container {
      margin-top: 15px;
      max-height: 350px;
      overflow-y: auto;
    }
    .result-container::-webkit-scrollbar { width: 4px; }
    .result-container::-webkit-scrollbar-thumb { background: #39C0E1; border-radius: 10px; }
    .record-table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.85rem;
    }
    .record-table th {
      padding: 10px 8px;
      border-bottom: 2px solid #333;
      color: #39C0E1;
      font-weight: 600;
      background: #222;
      position: sticky;
      top: 0;
    }
    .record-table td {
      padding: 10px 8px;
      border-bottom: 1px solid #333;
      color: #ccc;
    }
    .record-table tr:hover {
      background-color: rgba(57, 192, 225, 0.05);
    }
    .badge {
      background: rgba(57, 192, 225, 0.15);
      color: #39C0E1;
      padding: 3px 6px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: bold;
    }
    .empty-msg {
      text-align: center;
      color: #666;
      padding: 20px;
      font-size: 0.85rem;
    }
  </style>
</head>
<body>

  <div class="calculator">
    <h1>新北捷運三鶯線時刻表</h1>
    <div class="label-hint">請選擇您想要查詢的車站與行駛方向：</div>

    <div class="input-group">
      <label for="stationSelect">選擇車站</label>
      <select id="stationSelect">
        <option value="">-- 請選擇車站 --</option>
      </select>
    </div>

    <div class="input-group">
      <label for="directionSelect">行駛方向 (終點站)</label>
      <select id="directionSelect" disabled>
        <option value="">-- 請先選擇車站 --</option>
      </select>
    </div>

    <button class="calc-btn" id="searchBtn">查詢時刻表</button>

    <hr>

    <div style="display: flex; justify-content: space-between; align-items: center;">
      <span style="font-size: 0.85rem; color: #aaa;" id="resultCount">尚未查詢</span>
    </div>
    
    <div class="result-container">
      <table class="record-table">
        <thead>
          <tr>
            <th>序號</th>
            <th>到站時間</th>
            <th>發車時間</th>
            <th>終點站</th>
          </tr>
        </thead>
        <tbody id="timetableBody">
          <tr>
            <td colspan="4" class="empty-msg">請選擇條件並點擊查詢</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <script>
    // 自動嵌入完整三鶯線時刻表資料
    const sanyingData = """
    + json_str
    + """;

    document.addEventListener("DOMContentLoaded", () => {
      const stationSelect = document.getElementById("stationSelect");
      const stationsMap = new Map();
      
      sanyingData.forEach(item => {
        if (!stationsMap.has(item.StationID)) {
          stationsMap.set(item.StationID, item.StationName.Zh_tw);
        }
      });

      stationsMap.forEach((name, id) => {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = id + " " + name;
        stationSelect.appendChild(option);
      });
    });

    document.getElementById("stationSelect").addEventListener("change", function() {
      const stationId = this.value;
      const directionSelect = document.getElementById("directionSelect");
      directionSelect.innerHTML = '<option value="">-- 請選擇方向 --</option>';
      
      if (!stationId) {
        directionSelect.disabled = true;
        return;
      }

      // 取得該車站的所有目的地，並透過 Map 過濾重複項
      const availableDestinations = sanyingData.filter(item => item.StationID === stationId);
      const destMap = new Map();

      availableDestinations.forEach(item => {
        if (!destMap.has(item.DestinationStaionID)) {
          destMap.set(item.DestinationStaionID, item.DestinationStationName.Zh_tw);
        }
      });

      destMap.forEach((name, destId) => {
        const option = document.createElement("option");
        option.value = destId;
        option.textContent = "往 " + name;
        directionSelect.appendChild(option);
      });

      directionSelect.disabled = false;
    });

    document.getElementById("searchBtn").addEventListener("click", () => {
      const stationId = document.getElementById("stationSelect").value;
      const destId = document.getElementById("directionSelect").value;
      const tbody = document.getElementById("timetableBody");
      const resultCount = document.getElementById("resultCount");

      if (!stationId || !destId) {
        alert("請完整選擇車站與方向！");
        return;
      }

      const targetData = sanyingData.find(item => item.StationID === stationId && item.DestinationStaionID === destId);

      if (!targetData || !targetData.Timetables || targetData.Timetables.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-msg">查無相關時刻表資料</td></tr>';
        resultCount.textContent = "共 0 筆班次";
        return;
      }

      let html = "";
      targetData.Timetables.forEach(t => {
        html += '<tr>' +
          '<td><span class="badge">#' + t.Sequence + '</span></td>' +
          '<td>' + t.ArrivalTime + '</td>' +
          '<td><b>' + t.DepartureTime + '</b></td>' +
          '<td>' + targetData.DestinationStationName.Zh_tw + '</td>' +
          '</tr>';
      });

      tbody.innerHTML = html;
      resultCount.textContent = "查詢結果：共 " + targetData.Timetables.length + " 筆班次";
    });
  </script>
</body>
</html>
"""
)

# 4. 輸出成 index.html
with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)

print("成功產生 index.html（主題色已更新為 #39C0E1）！")
