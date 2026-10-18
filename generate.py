import json

# 1. 讀取包含平日與例假日的單一 JSON 檔案
with open("sanying_timetable.json", "r", encoding="utf-8-sig") as f:
  raw_data = json.load(f)

stations_ordered = [
    ("LB01", "頂埔"),
    ("LB02", "媽祖田"),
    ("LB03", "長壽山"),
    ("LB04", "橫溪"),
    ("LB05", "龍埔"),
    ("LB06", "三峽"),
    ("LB07", "台北大學"),
    ("LB08", "鶯歌車站"),
    ("LB09", "陶瓷老街"),
    ("LB10", "國華"),
    ("LB11", "永吉公園"),
    ("LB12", "鶯桃福德"),
]
station_map = {s_id: s_name for s_id, s_name in stations_ordered}


def time_to_min(t_str):
  if not t_str or ":" not in t_str:
    return -1
  h, m = map(int, t_str.split(":"))
  return h * 60 + m


# 2. 解析單一檔案資料，自動依 ServiceTag 分類平日與例假日
combined_display_data = []

for station in raw_data:
  # 取得服務日標籤（相容 ServiceTag 或 ServiceDay 結構）
  tag = station.get("ServiceTag")
  if not tag and "ServiceDay" in station:
    if isinstance(station["ServiceDay"], dict):
      tag = station["ServiceDay"].get("ServiceTag") or station[
          "ServiceDay"
      ].get("Name")
    else:
      tag = station["ServiceDay"]

  # 標準化標籤名稱
  service_tag = "平日" if tag in ["平日", "Weekday", "正常營運日"] else "例假日"

  s_id = station.get("StationID")
  s_name = station_map.get(
      s_id,
      station.get("StationName", {}).get("Zh_tw", s_id)
      if isinstance(station.get("StationName"), dict)
      else s_id,
  )
  dest_id = station.get("DestinationStaionID")
  dest_name = (
      "鶯桃福德"
      if dest_id == "LB12"
      else ("頂埔" if dest_id == "LB01" else dest_id)
  )

  # 整理並排序該站該方向的時刻表
  raw_timetables = station.get("Timetables", [])
  sorted_timetables = sorted(
      raw_timetables, key=lambda x: time_to_min(x.get("DepartureTime", ""))
  )

  station_timetables = []
  for seq, t_obj in enumerate(sorted_timetables, start=1):
    station_timetables.append({
        "Sequence": seq,
        "ArrivalTime": t_obj.get("ArrivalTime", ""),
        "DepartureTime": t_obj.get("DepartureTime", ""),
    })

  combined_display_data.append({
      "ServiceTag": service_tag,
      "StationID": s_id,
      "StationName": {"Zh_tw": s_name},
      "DestinationStaionID": dest_id,
      "DestinationStationName": {"Zh_tw": dest_name},
      "Timetables": station_timetables,
  })

json_str = json.dumps(combined_display_data, ensure_ascii=False)

# 3. 輸出簡化、純時刻表的 HTML 介面
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
      background: #1e1e1e; 
      color: #e0e0e0; 
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
      display: flex; 
      justify-content: center; 
      padding: 12px; 
      width: 100%;   
      min-height: 100vh;
    }
    .calculator { 
      background: #1e1e1e; 
      padding: 0px; 
      width: 100%;       
      max-width: 700px; 
      border: none; 
      box-shadow: none; 
      overflow: hidden;  
    }
    h1 { font-size: 1.25rem; color: #39C0E1; text-align: center; margin: 0 0 15px; }
    .label-hint { font-size: 0.8rem; color: #888; margin-bottom: 10px; }
    .input-group { margin-bottom: 15px; }
    label { display: block; font-size: 0.82rem; margin-bottom: 6px; color: #aaa; }
    select { 
      width: 100%; 
      padding: 11px; 
      background: #252525; 
      border: 1px solid #444; 
      border-radius: 8px; 
      color: #fff; 
      outline: none; 
      font-size: 0.95rem;
    }
    select:focus { border-color: #39C0E1; }
    
    /* 營運日切換按鈕群組 */
    .day-selector {
      display: flex;
      gap: 10px;
      margin-bottom: 15px;
    }
    .day-btn {
      flex: 1;
      padding: 10px;
      background: #252525;
      border: 1px solid #444;
      border-radius: 8px;
      color: #aaa;
      font-weight: bold;
      cursor: pointer;
      font-size: 0.9rem;
      transition: all 0.2s;
    }
    .day-btn.active {
      background: #39C0E1;
      color: #121212;
      border-color: #39C0E1;
    }

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
      max-height: 450px;
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
      background-color: rgba(57, 192, 225, 0.08);
    }
    .highlight-row {
      background-color: rgba(57, 192, 225, 0.15) !important;
    }
    .highlight-row td {
      color: #39C0E1 !important;
      font-weight: bold;
    }
    .badge {
      background: rgba(57, 192, 225, 0.15);
      color: #39C0E1;
      padding: 3px 6px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: bold;
    }
    .next-badge {
      background: #39C0E1;
      color: #121212;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.7rem;
      font-weight: bold;
      margin-left: 6px;
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
    <div class="label-hint">請選擇營運日、車站與行駛方向：</div>

    <!-- 平日 / 例假日 切換按鈕 -->
    <div class="day-selector">
      <button class="day-btn active" id="btn-weekday">平日</button>
      <button class="day-btn" id="btn-holiday">例假日</button>
    </div>

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
    
    <div class="result-container" id="resultContainer">
      <table class="record-table">
        <thead>
          <tr>
            <th>班次序號</th>
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
    const allSanyingData = """ + json_str + """;
    let currentServiceTag = "平日";

    function updateStationOptions() {
      const stationSelect = document.getElementById("stationSelect");
      const currentSelectedStation = stationSelect.value;
      stationSelect.innerHTML = '<option value="">-- 請選擇車站 --</option>';
      
      const stationsMap = new Map();
      const filteredData = allSanyingData.filter(item => item.ServiceTag === currentServiceTag);

      filteredData.forEach(item => {
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

      if (stationsMap.has(currentSelectedStation)) {
        stationSelect.value = currentSelectedStation;
      } else {
        document.getElementById("directionSelect").innerHTML = '<option value="">-- 請先選擇車站 --</option>';
        document.getElementById("directionSelect").disabled = true;
      }
    }

    document.addEventListener("DOMContentLoaded", () => {
      updateStationOptions();

      document.getElementById("btn-weekday").addEventListener("click", function() {
        document.getElementById("btn-holiday").classList.remove("active");
        this.classList.add("active");
        currentServiceTag = "平日";
        updateStationOptions();
      });

      document.getElementById("btn-holiday").addEventListener("click", function() {
        document.getElementById("btn-weekday").classList.remove("active");
        this.classList.add("active");
        currentServiceTag = "例假日";
        updateStationOptions();
      });
    });

    document.getElementById("stationSelect").addEventListener("change", function() {
      const stationId = this.value;
      const directionSelect = document.getElementById("directionSelect");
      directionSelect.innerHTML = '<option value="">-- 請先選擇方向 --</option>';
      
      if (!stationId) {
        directionSelect.disabled = true;
        return;
      }

      const filteredData = allSanyingData.filter(item => item.ServiceTag === currentServiceTag);
      const availableDestinations = filteredData.filter(item => item.StationID === stationId);
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

      const filteredData = allSanyingData.filter(item => item.ServiceTag === currentServiceTag);
      const targetData = filteredData.find(item => item.StationID === stationId && item.DestinationStaionID === destId);

      if (!targetData || !targetData.Timetables || targetData.Timetables.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-msg">查無相關時刻表資料</td></tr>';
        resultCount.textContent = "共 0 筆班次";
        return;
      }

      const now = new Date();
      const currentHours = String(now.getHours()).padStart(2, '0');
      const currentMinutes = String(now.getMinutes()).padStart(2, '0');
      const currentTimeStr = currentHours + ":" + currentMinutes;

      let nextIndex = targetData.Timetables.findIndex(t => t.DepartureTime >= currentTimeStr);
      if (nextIndex === -1) { nextIndex = 0; }

      let html = "";
      targetData.Timetables.forEach((t, index) => {
        const isNext = (index === nextIndex);
        const rowClass = isNext ? ' class="highlight-row"' : '';
        const badgeTag = isNext ? '<span class="next-badge">最近班次</span>' : '';
        
        html += '<tr' + rowClass + '>' +
          '<td><span class="badge"># ' + t.Sequence + '</span></td>' +
          '<td>' + t.ArrivalTime + '</td>' +
          '<td><b>' + t.DepartureTime + '</b>' + badgeTag + '</td>' +
          '<td>' + targetData.DestinationStationName.Zh_tw + '</td>' +
          '</tr>';
      });

      tbody.innerHTML = html;
      resultCount.textContent = "查詢結果 (" + currentServiceTag + ")：共 " + targetData.Timetables.length + " 筆班次";

      setTimeout(() => {
        const highlightedRow = tbody.querySelector('.highlight-row');
        if (highlightedRow) {
          highlightedRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);
    });
  </script>
</body>
</html>
"""
)

with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)

print(
    "成功讀取單一檔案 (sanying_timetable.json)，並生成帶有「平日」與「例假日」切換按鈕的"
    " index.html！"
)
