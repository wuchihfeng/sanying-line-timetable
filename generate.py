import json

# 1. 分別讀取平日與例假日的獨立 JSON 檔案
with open("sanying_timetable_weekday.json", "r", encoding="utf-8-sig") as f:
  weekday_data = json.load(f)

with open("sanying_timetable_holiday.json", "r", encoding="utf-8-sig") as f:
  holiday_data = json.load(f)

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


def process_dataset(raw_data, tag_name):
  station_time_map = {}
  for station in raw_data:
    s_id = station["StationID"]
    dest_id = station["DestinationStaionID"]
    if s_id not in station_time_map:
      station_time_map[s_id] = {}
    if dest_id not in station_time_map[s_id]:
      station_time_map[s_id][dest_id] = {}

    for t in station.get("Timetables", []):
      station_time_map[s_id][dest_id][t["DepartureTime"]] = t

  events_by_dest = {"LB12": [], "LB01": []}
  for s_id, s_name in stations_ordered:
    for dest_id in ["LB12", "LB01"]:
      if s_id in station_time_map and dest_id in station_time_map[s_id]:
        for dep_t in station_time_map[s_id][dest_id]:
          events_by_dest[dest_id].append({
              "station_id": s_id,
              "dep_time": dep_t,
              "dep_min": time_to_min(dep_t),
              "station_index": station_indices[s_id],
          })

  trips_lookup = {}
  for dest_id in ["LB12", "LB01"]:
    events = events_by_dest[dest_id]
    events.sort(key=lambda x: (x["dep_min"], x["station_index"]))

    dest_name = "鶯桃福德" if dest_id == "LB12" else "頂埔"
    is_heading_yingge = dest_id == "LB12"

    for idx, ev in enumerate(events):
      sys_seq = idx + 1
      s_id = ev["station_id"]
      dep_t = ev["dep_time"]

      trip_key = f"{tag_name}_{dest_id}_{s_id}_{dep_t}_{sys_seq}"

      check_stations = (
          stations_ordered
          if is_heading_yingge
          else list(reversed(stations_ordered))
      )
      start_pos = -1
      for p, (cs_id, _) in enumerate(check_stations):
        if cs_id == s_id:
          start_pos = p
          break

      collected_stops = []
      curr_ref_min = ev["dep_min"]

      if start_pos != -1:
        for p in range(start_pos, len(check_stations)):
          check_s_id, check_s_name = check_stations[p]
          if (
              check_s_id in station_time_map
              and dest_id in station_time_map[check_s_id]
          ):
            dest_t_map = station_time_map[check_s_id][dest_id]
            best_match = None
            min_diff = 999

            for d_time, d_obj in dest_t_map.items():
              d_min = time_to_min(d_time)
              diff = d_min - curr_ref_min
              if 1 <= diff <= 25 and diff < min_diff:
                min_diff = diff
                best_match = d_obj

            if check_s_id == s_id and dep_t in dest_t_map:
              best_match = dest_t_map[dep_t]

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
          "SystemSeq": sys_seq,
          "DepartureTime": dep_t,
          "StartStation": station_map.get(s_id, s_id),
          "Stops": [
              {
                  "StationID": st["StationID"],
                  "StationName": st["StationName"],
                  "ArrivalTime": st["ArrivalTime"],
                  "DepartureTime": st["DepartureTime"],
              }
              for st in collected_stops
          ],
      }

      ev["trip_key"] = trip_key
      ev["sys_seq"] = sys_seq

  station_display_data = []
  for s_id, s_name in stations_ordered:
    for dest_id in ["LB12", "LB01"]:
      if s_id in station_time_map and dest_id in station_time_map[s_id]:
        dest_name = "鶯桃福德" if dest_id == "LB12" else "頂埔"
        station_timetables = []

        station_deps = sorted(
            list(station_time_map[s_id][dest_id].keys()), key=time_to_min
        )

        for t_item_dep in station_deps:
          t_obj = station_time_map[s_id][dest_id][t_item_dep]

          matched_trip_key = ""
          matched_seq = 1
          for ev in events_by_dest[dest_id]:
            if ev["station_id"] == s_id and ev["dep_time"] == t_item_dep:
              matched_trip_key = ev["trip_key"]
              matched_seq = ev["sys_seq"]
              break

          station_timetables.append({
              "Sequence": matched_seq,
              "ArrivalTime": t_obj["ArrivalTime"],
              "DepartureTime": t_obj["DepartureTime"],
              "TripKey": matched_trip_key,
          })

        station_display_data.append({
            "ServiceTag": tag_name,
            "StationID": s_id,
            "StationName": {"Zh_tw": s_name},
            "DestinationStaionID": dest_id,
            "DestinationStationName": {"Zh_tw": dest_name},
            "Timetables": station_timetables,
        })

  return station_display_data, trips_lookup


# 2. 分別處理平日與假日資料
weekday_display, weekday_trips = process_dataset(weekday_data, "平日")
holiday_display, holiday_trips = process_dataset(holiday_data, "例假日")

combined_display_data = weekday_display + holiday_display
all_trips_lookup = {"平日": weekday_trips, "例假日": holiday_trips}

json_str = json.dumps(combined_display_data, ensure_ascii=False)
trips_str = json.dumps(all_trips_lookup, ensure_ascii=False)

# 3. 輸出 HTML (包含 平日 與 例假日 按鈕)
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
    <div class="label-hint">請選擇營運日、車站與行駛方向：</div>

    <!-- 平日 / 例假日 切換按鈕 -->
    <div class="day-selector">
      <button class="day-btn active" id="sanying-timetable-weekday">平日</button>
      <button class="day-btn" id="sanying-timetable-holiday">例假日</button>
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
    const allSanyingData = """ + json_str + """;
    const allTripsLookup = """ + trips_str + """;

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

      document.getElementById("sanying-timetable-weekday").addEventListener("click", function() {
        document.getElementById("sanying-timetable-holiday").classList.remove("active");
        this.classList.add("active");
        currentServiceTag = "平日";
        updateStationOptions();
      });

      document.getElementById("sanying-timetable-holiday").addEventListener("click", function() {
        document.getElementById("sanying-timetable-weekday").classList.remove("active");
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
        
        const tripKey = t.TripKey;

        html += '<tr' + rowClass + ' data-trip="' + tripKey + '">' +
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

      tbody.querySelectorAll('tr[data-trip]').forEach(tr => {
        tr.addEventListener('click', function() {
          const tKey = this.getAttribute('data-trip');
          const tripsLookup = allTripsLookup[currentServiceTag];
          const tripInfo = tripsLookup[tKey];
          
          if (!tripInfo || !tripInfo.Stops || tripInfo.Stops.length === 0) {
            alert('查無此車次的詳細行經站紀錄');
            return;
          }

          document.getElementById('modalTitle').textContent = "系統車次 #" + tripInfo.SystemSeq + " 往 " + tripInfo.DestinationName + " (" + tripInfo.StartStation + " 發車: " + tripInfo.DepartureTime + ")";
          
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

print(
    "成功讀取兩個獨立檔案 (sanying_timetable_weekday.json 與"
    " sanying_timetable_holiday.json)，並生成帶有「平日」與「例假日」按鈕的"
    " index.html！"
)
