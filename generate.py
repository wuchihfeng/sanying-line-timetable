import json

# 1. 讀取三鶯線完整 JSON 檔
with open("sanying_timetable.json", "r", encoding="utf-8-sig") as f:
  full_data = json.load(f)

# 2. 建立站點順序對照表 (LB01 -> LB12)
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

# 3. 建立 station_time_index: [station_id][dest_id][dep_time] = timetable_item
station_time_index = {}
for station in full_data:
  s_id = station["StationID"]
  dest_id = station["DestinationStaionID"]
  if s_id not in station_time_index:
    station_time_index[s_id] = {}
  if dest_id not in station_time_index[s_id]:
    station_time_index[s_id][dest_id] = {}

  for t in station.get("Timetables", []):
    station_time_index[s_id][dest_id][t["DepartureTime"]] = t

# 4. 時序接龍與軌跡推導引擎
# 目標：為每一筆單站發車紀錄，向前/向後推導出它在整條線上完整的停靠足跡
trips_lookup = {}

for station in full_data:
  s_id = station["StationID"]
  dest_id = station["DestinationStaionID"]
  dest_name = station["DestinationStationName"]["Zh_tw"]

  for t in station.get("Timetables", []):
    dep_time = t["DepartureTime"]
    trip_key = f"{dest_id}_{dep_time}_{t['Sequence']}"

    if trip_key in trips_lookup:
      continue

    # 開始進行時序接龍推導：找出這班車在全線各站的停靠時間
    stops = []
    current_time = dep_time
    
    # 決定搜尋方向：若終點是鶯歌/鶯桃福德(LB12等)，方向通常由北向南；若往頂埔(LB01)，方向由南向北
    # 我們根據站點代號排序進行匹配
    is_heading_up = (dest_id == "LB01")
    search_stations = sorted(stations_ordered, key=lambda x: x[0], reverse=is_heading_up)

    # 為了確保能抓出整條線的軌跡，我們用時間差與序號進行嚴格比對
    # 尋找每一個站點上有沒有時間合理銜接的班次
    matched_stops = []
    for st_id, st_name in search_stations:
      if st_id in station_time_index and dest_id in station_time_index[st_id]:
        dest_dict = station_time_index[st_id][dest_id]
        # 尋找相同 Sequence 或者是發車時間最接近的紀錄
        found = None
        for d_time, t_obj in dest_dict.items():
          if t_obj["Sequence"] == t["Sequence"]:
            found = t_obj
            break
        
        if found:
          matched_stops.append({
              "StationID": st_id,
              "StationName": st_name,
              "ArrivalTime": found["ArrivalTime"],
              "DepartureTime": found["DepartureTime"],
          })

    # 依照站點代號重新排序確保由小到大 (LB01 -> LB12) 完整呈現整條線的行經站
    matched_stops.sort(key=lambda x: x["StationID"])

    trips_lookup[trip_key] = {
        "DestinationName": dest_name,
        "Sequence": t["Sequence"],
        "DepartureTime": dep_time,
        "Stops": matched_stops,
    }

# 5. 轉成 JSON 格式
json_str = json.dumps(full_data, ensure_ascii=False)
trips_str = json.dumps(trips_lookup, ensure_ascii=False)

# 6. 組合前端 HTML
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
      cursor: pointer;
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
    /* 彈窗樣式 */
    .modal {
      display: none;
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.7);
      justify-content: center;
      align-items: center;
      padding: 16px;
      z-index: 1000;
    }
    .modal-content {
      background: #222;
      border: 1px solid #39C0E1;
      border-radius: 12px;
      width: 100%;
      max-width: 480px;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .modal-header {
      padding: 15px;
      background: #282828;
      border-bottom: 1px solid #333;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-header h3 { margin: 0; font-size: 1rem; color: #39C0E1; }
    .close-btn { background: none; border: none; color: #aaa; font-size: 1.2rem; cursor: pointer; }
    .modal-body { padding: 15px; overflow-y: auto; }
    .stop-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .stop-table th, .stop-table td { padding: 8px; border-bottom: 1px solid #333; text-align: left; }
    .stop-table th { color: #39C0E1; background: #1e1e1e; }
  </style>
</head>
<body>

  <div class="calculator">
    <h1>新北捷運三鶯線時刻表</h1>
    <div class="label-hint">請選擇您想要查詢的車站與行駛方向（點擊任一班次可檢視全線完整停靠站）：</div>

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

  <!-- 全線停靠站彈窗 -->
  <div class="modal" id="tripModal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 id="modalTitle">車次完整行經站</h3>
        <button class="close-btn" id="closeModal">&times;</button>
      </div>
      <div class="modal-body">
        <table class="stop-table">
          <thead>
            <tr>
              <th>車站</th>
              <th>到站時間</th>
              <th>發車時間</th>
            </tr>
          </thead>
          <tbody id="modalBody">
            <!-- 動態插入完整停靠站 -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const sanyingData = """
    + json_str
    + """;
    const tripsLookup = """
    + trips_str
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
        
        const tripKey = destId + "_" + t.DepartureTime + "_" + t.Sequence;

        html += '<tr' + rowClass + ' data-trip="' + tripKey + '">' +
          '<td><span class="badge">#' + t.Sequence + '</span></td>' +
          '<td>' + t.ArrivalTime + '</td>' +
          '<td><b>' + t.DepartureTime + '</b>' + badgeTag + '</td>' +
          '<td>' + targetData.DestinationStationName.Zh_tw + '</td>' +
          '</tr>';
      });

      tbody.innerHTML = html;
      resultCount.textContent = "查詢結果：共 " + targetData.Timetables.length + " 筆班次 (點擊任一班次可看全線行經站)";

      setTimeout(() => {
        const highlightedRow = tbody.querySelector('.highlight-row');
        if (highlightedRow) {
          highlightedRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);

      tbody.querySelectorAll('tr[data-trip]').forEach(tr => {
        tr.addEventListener('click', function() {
          const tKey = this.getAttribute('data-trip');
          const tripInfo = tripsLookup[tKey];
          if (!tripInfo || !tripInfo.Stops || tripInfo.Stops.length === 0) {
            alert('查無此車次的完整行經站紀錄');
            return;
          }

          document.getElementById('modalTitle').textContent = "車次 #" + tripInfo.Sequence + " 往 " + tripInfo.DestinationName + " (發車: " + tripInfo.DepartureTime + ")";
          
          let stopHtml = "";
          tripInfo.Stops.forEach(stop => {
            stopHtml += '<tr>' +
              '<td>' + stop.StationID + ' ' + stop.StationName + '</td>' +
              '<td>' + stop.ArrivalTime + '</td>' +
              '<td><b>' + stop.DepartureTime + '</b></td>' +
              '</tr>';
          });
          document.getElementById('modalBody').innerHTML = stopHtml;
          document.getElementById('tripModal').style.display = 'flex';
        });
      });
    });

    document.getElementById('closeModal').addEventListener('click', () => {
      document.getElementById('tripModal').style.display = 'none';
    });
    window.addEventListener('click', (e) => {
      const modal = document.getElementById('tripModal');
      if (e.target === modal) { modal.style.display = 'none'; }
    });
  </script>
</body>
</html>
"""
)

# 7. 輸出成 index.html
with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)

print("成功產生 index.html！")
