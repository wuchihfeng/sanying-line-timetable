import json

# 1. 讀取三鶯線完整 JSON 檔
with open("sanying_timetable.json", "r", encoding="utf-8-sig") as f:
  full_data = json.load(f)

# 2. 定義三鶯線標準站點順序 (LB01 -> LB12)
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
station_indices = {s_id: idx for idx, (s_id, _) in enumerate(stations_ordered)}


def time_to_min(t_str):
  if not t_str or ":" not in t_str:
    return -1
  h, m = map(int, t_str.split(":"))
  return h * 60 + m


# 3. 建立全域時間索引
time_index = {}
for station in full_data:
  s_id = station["StationID"]
  dest_id = station["DestinationStaionID"]
  if s_id not in time_index:
    time_index[s_id] = {}
  if dest_id not in time_index[s_id]:
    time_index[s_id][dest_id] = []

  for t in station.get("Timetables", []):
    dep_m = time_to_min(t["DepartureTime"])
    arr_m = time_to_min(t["ArrivalTime"])
    time_index[s_id][dest_id].append({
        "ArrivalTime": t["ArrivalTime"],
        "DepartureTime": t["DepartureTime"],
        "DepMin": dep_m,
        "ArrMin": arr_m,
    })

# 4. 實際發車起點至終點的精準推導引擎（支援多點發車、絕不亂湊前段站）
trips_lookup = {}

for station in full_data:
  s_id = station["StationID"]
  dest_id = station["DestinationStaionID"]
  dest_name = station["DestinationStationName"]["Zh_tw"]

  for t in station.get("Timetables", []):
    base_dep_str = t["DepartureTime"]
    base_dep_min = time_to_min(base_dep_str)
    trip_key = f"{dest_id}_{base_dep_str}_{t['Sequence']}"

    if trip_key in trips_lookup:
      continue

    is_heading_to_yingge = dest_id == "LB12"
    route_indices = (
        list(range(len(stations_ordered)))
        if is_heading_to_yingge
        else list(range(len(stations_ordered) - 1, -1, -1))
    )

    current_s_idx = station_indices.get(s_id, 0)
    matched_stops = {}

    # 放入當前點
    matched_stops[s_id] = {
        "StationID": s_id,
        "StationName": station_map.get(s_id, s_id),
        "ArrivalTime": t["ArrivalTime"],
        "DepartureTime": t["DepartureTime"],
        "SortMin": base_dep_min,
    }

    # A. 順著行進方向往後找後續站點
    ref_min = base_dep_min
    start_pos = route_indices.index(current_s_idx)
    for pos in range(start_pos + 1, len(route_indices)):
      st_idx = route_indices[pos]
      st_id, st_name = stations_ordered[st_idx]

      if st_id in time_index and dest_id in time_index[st_id]:
        candidates = time_index[st_id][dest_id]
        valid = [c for c in candidates if 0 < (c["DepMin"] - ref_min) <= 12]
        if valid:
          best = min(valid, key=lambda x: x["DepMin"] - ref_min)
          matched_stops[st_id] = {
              "StationID": st_id,
              "StationName": st_name,
              "ArrivalTime": best["ArrivalTime"],
              "DepartureTime": best["DepartureTime"],
              "SortMin": best["DepMin"],
          }
          ref_min = best["DepMin"]
        else:
          break

    # B. 順著行進方向往前找前段站（只有當資料庫中確實有該車次的連續發車紀錄時才串聯，否則視為多點發車起點，不強行亂湊）
    ref_min = base_dep_min
    for pos in range(start_pos - 1, -1, -1):
      st_idx = route_indices[pos]
      st_id, st_name = stations_ordered[st_idx]

      if st_id in time_index and dest_id in time_index[st_id]:
        candidates = time_index[st_id][dest_id]
        valid = [c for c in candidates if 0 < (ref_min - c["DepMin"]) <= 12]
        if valid:
          best = min(valid, key=lambda x: ref_min - x["DepMin"])
          matched_stops[st_id] = {
              "StationID": st_id,
              "StationName": st_name,
              "ArrivalTime": best["ArrivalTime"],
              "DepartureTime": best["DepartureTime"],
              "SortMin": best["DepMin"],
          }
          ref_min = best["DepMin"]
        else:
          break  # 前方無連續發車紀錄，代表此處即為該車次的實際起點站（多點發車）

    # 將收集到的站點依照物理順序排列
    final_stops_list = []
    for st_id, st_name in stations_ordered:
      if st_id in matched_stops:
        final_stops_list.append(matched_stops[st_id])

    if not is_heading_to_yingge:
      final_stops_list.sort(key=lambda x: station_indices[x["StationID"]], reverse=True)
    else:
      final_stops_list.sort(key=lambda x: station_indices[x["StationID"]])

    trips_lookup[trip_key] = {
        "DestinationName": dest_name,
        "Sequence": t["Sequence"],
        "DepartureTime": base_dep_str,
        "Stops": final_stops_list,
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
    <div class="label-hint">請選擇您想要查詢的車站與行駛方向（點擊任一班次可檢視實際行經站點）：</div>

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
        <h3 id="modalTitle">車次實際行經站</h3>
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
            <!-- 動態插入實際行經站 -->
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
      directionSelect.innerHTML = '<option value="">-- 請先選擇方向 --</option>';
      
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
      resultCount.textContent = "查詢結果：共 " + targetData.Timetables.length + " 筆班次 (點擊可看實際行經站)";

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
            alert('查無此車次的詳細行經站紀錄');
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

print("成功產生支援多點發車、只顯示實際行經站點的 index.html！")
