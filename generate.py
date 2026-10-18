import json

# 1. 讀取三鶯線完整 JSON 檔
with open("sanying_timetable.json", "r", encoding="utf-8-sig") as f:
  full_data = json.load(f)

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


# 2. 建立全域車站時間索引：station_time_map[station_id][dest_id][dep_time] = 該筆時刻物件
station_time_map = {}
for station in full_data:
  s_id = station["StationID"]
  dest_id = station["DestinationStaionID"]
  if s_id not in station_time_map:
    station_time_map[s_id] = {}
  if dest_id not in station_time_map[s_id]:
    station_time_map[s_id][dest_id] = {}

  for t in station.get("Timetables", []):
    station_time_map[s_id][dest_id][t["DepartureTime"]] = t

# 3. 核心：收集各方向所有出現過的時間點，排好時刻，賦予「三鶯線系統全域車次編號」
# 結構：master_trips[dest_id] = [ { "system_seq": 1, "base_time": "06:00", ... }, ... ]
master_trips = {"LB12": [], "LB01": []}

for dest_id in ["LB12", "LB01"]:
  # 收集該方向全系統所有車站出現過的發車時間
  all_times = set()
  for s_id in station_time_map:
    if dest_id in station_time_map[s_id]:
      for dep_t in station_time_map[s_id][dest_id]:
        all_times.add(dep_t)

  # 排時刻：依照時間先後排序
  sorted_times = sorted(list(all_times), key=time_to_min)

  # 給予車次編號（三鶯線系統的第幾班車）
  for idx, base_time in enumerate(sorted_times):
    sys_seq = idx + 1
    master_trips[dest_id].append({
        "system_seq": sys_seq,
        "base_time": base_time,
        "dest_id": dest_id,
        "dest_name": "鶯桃福德" if dest_id == "LB12" else "頂埔",
    })

# 4. 建立 trips_lookup 與各站時刻表檢視對應
trips_lookup = {}
# 同時我們需要讓前端在查詢某站時，能知道該站的每一個發車時間對應到全系統第幾班車
station_display_data = []

# 我們反向為每個車站產生對應的列表
for s_id, s_name in stations_ordered:
  for dest_id in ["LB12", "LB01"]:
    if s_id in station_time_map and dest_id in station_time_map[s_id]:
      dest_name = "鶯桃福德" if dest_id == "LB12" else "頂埔"
      station_timetables = []

      # 取得該站該方向的所有發車時間
      station_deps = sorted(
          list(station_time_map[s_id][dest_id].keys()), key=time_to_min
      )

      for t_item_dep in station_deps:
        t_obj = station_time_map[s_id][dest_id][t_item_dep]

        # 找出這個發車時間對應到全系統第幾班車 (system_seq)
        matched_sys_seq = 1
        for mt in master_trips[dest_id]:
          if mt["base_time"] == t_item_dep:
            matched_sys_seq = mt["system_seq"]
            break

        trip_key = f"{dest_id}_{t_item_dep}_{matched_sys_seq}"

        # 嚴格依據資料抓取該全域車次在各站實際存在的紀錄
        collected_stops = []
        is_heading_yingge = dest_id == "LB12"
        check_stations = (
            stations_ordered
            if is_heading_yingge
            else list(reversed(stations_ordered))
        )

        curr_ref_min = time_to_min(t_item_dep)
        for check_s_id, check_s_name in check_stations:
          if (
              check_s_id in station_time_map
              and dest_id in station_time_map[check_s_id]
          ):
            dest_t_map = station_time_map[check_s_id][dest_id]
            # 尋找時間差在合理範圍內的站點紀錄
            best_match = None
            min_diff = 999
            for d_time, d_obj in dest_t_map.items():
              diff = abs(time_to_min(d_time) - curr_ref_min)
              if diff < min_diff and diff <= 15:
                min_diff = diff
                best_match = d_obj

            if best_match:
              collected_stops.append({
                  "StationID": check_s_id,
                  "StationName": check_s_name,
                  "ArrivalTime": best_match["ArrivalTime"],
                  "DepartureTime": best_match["DepartureTime"],
                  "Index": station_indices[check_s_id],
              })
              curr_ref_min = time_to_min(best_match["DepartureTime"])

        collected_stops.sort(
            key=lambda x: x["Index"],
            reverse=(not is_heading_yingge),
        )

        trips_lookup[trip_key] = {
            "DestinationName": dest_name,
            "SystemSeq": matched_sys_seq,
            "DepartureTime": t_item_dep,
            "Stops": [
                {
                    "StationID": s["StationID"],
                    "StationName": s["StationName"],
                    "ArrivalTime": s["ArrivalTime"],
                    "DepartureTime": s["DepartureTime"],
                }
                for s in collected_stops
            ],
        }

        station_timetables.append({
            "Sequence": matched_sys_seq,  # 顯示全系統車次編號
            "ArrivalTime": t_obj["ArrivalTime"],
            "DepartureTime": t_obj["DepartureTime"],
            "TripKey": trip_key,
        })

      station_display_data.append({
          "StationID": s_id,
          "StationName": {"Zh_tw": s_name},
          "DestinationStaionID": dest_id,
          "DestinationStationName": {"Zh_tw": dest_name},
          "Timetables": station_timetables,
      })

# 5. 輸出 JSON 與 HTML
json_str = json.dumps(station_display_data, ensure_ascii=False)
trips_str = json.dumps(trips_lookup, ensure_ascii=False)

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
    
    <div class="result-container" id="resultContainer">
      <table class="record-table">
        <thead>
          <tr>
            <th>系統車次</th>
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
        <h3 id="modalTitle">系統車次行經站</h3>
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
            <!-- 動態插入 -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const sanyingData = """ + json_str + """;
    const tripsLookup = """ + trips_str + """;

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
        
        const tripKey = t.TripKey;

        html += '<tr' + rowClass + ' data-trip="' + tripKey + '">' +
          '<td><span class="badge"># ' + t.Sequence + '</span></td>' +
          '<td>' + t.ArrivalTime + '</td>' +
          '<td><b>' + t.DepartureTime + '</b>' + badgeTag + '</td>' +
          '<td>' + targetData.DestinationStationName.Zh_tw + '</td>' +
          '</tr>';
      });

      tbody.innerHTML = html;
      resultCount.textContent = "查詢結果：共 " + targetData.Timetables.length + " 筆班次";

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

          document.getElementById('modalTitle').textContent = "系統車次 #" + tripInfo.SystemSeq + " 往 " + tripInfo.DestinationName + " (發車: " + tripInfo.DepartureTime + ")";
          
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

with open("index.html", "w", encoding="utf-8") as f:
  f.write(html_content)

print("成功產生以系統全域車次編號為主的完美 index.html！")
