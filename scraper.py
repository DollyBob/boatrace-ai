import os
import json
import re
import datetime
import urllib.request
from bs4 import BeautifulSoup

now_utc = datetime.datetime.now(datetime.timezone.utc)
jst_now = now_utc + datetime.timedelta(hours=9)
today_str = jst_now.strftime("%Y-%m-%d")
ymd_str = jst_now.strftime("%Y%m%d")

VENUES_MASTER = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川",
    "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国",
    "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀",
    "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_html(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read()
            for enc in ["utf-8", "euc-jp", "shift_jis", "cp932"]:
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Fetch Error: {url} -> {e}")
        return None

def get_active_venues():
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={ymd_str}"
    html = fetch_html(url)
    found = set()
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["a", "img", "tr"], href=True):
            m = re.search(r"jcd=(\d{2})", tag["href"])
            if m and m.group(1) in VENUES_MASTER:
                found.add(m.group(1))
        for tag in soup.find_all(["img", "source"], src=True):
            m = re.search(r"jcd=(\d{2})", tag["src"])
            if m and m.group(1) in VENUES_MASTER:
                found.add(m.group(1))
        for code, name in VENUES_MASTER.items():
            if f"jcd={code}" in html:
                found.add(code)

    res = sorted(list(found))
    return res if len(res) > 0 else ["01", "02", "03", "04"]

def get_race_data(jcd, rno):
    scores = {1: 45.0, 2: 18.0, 3: 15.0, 4: 12.0, 5: 6.0, 6: 4.0}
    sorted_boats = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    b1, b2, b3, b4 = sorted_boats[0], sorted_boats[1], sorted_boats[2], sorted_boats[3]

    honmei = f"{b1}-{b2}-{b3}"
    chuan = f"{b2}-{b1}-{b3}"
    oana = f"{b3}-{b1}-{b4}"

    result_url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd}&hd={ymd_str}"
    res_html = fetch_html(result_url)
    actual_res = ""
    actual_pay = 0
    if res_html:
        soup_res = BeautifulSoup(res_html, "html.parser")
        for tr in soup_res.select("table tbody tr"):
            text = tr.get_text()
            if "3連単" in text:
                m_comb = re.search(r"([1-6]-[1-6]-[1-6])", text)
                m_pay = re.search(r"([0-9,]{3,})円", text)
                if m_comb:
                    actual_res = m_comb.group(1)
                if m_pay:
                    actual_pay = int(m_pay.group(1).replace(",", ""))
                break

    return {
        "honmei": honmei,
        "chuan": chuan,
        "oana": oana,
        "result": actual_res,
        "payout": actual_pay
    }

def main():
    venues = get_active_venues()
    print(f"Active venues: {len(venues)} -> {venues}")

    data_output = {
        "date": today_str,
        "venue_count": len(venues),
        "total_races": len(venues) * 12,
        "venues": {}
    }

    for jcd in venues:
        if jcd not in VENUES_MASTER:
            continue
        v_name = VENUES_MASTER[jcd]
        data_output["venues"][v_name] = {}
        for r in range(1, 13):
            data_output["venues"][v_name][f"{r}R"] = get_race_data(jcd, r)

    history_file = "history.json"
    history_data = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            history_data = {}

    finished_cnt = 0
    h_cnt, c_cnt, o_cnt = 0, 0, 0
    total_pay = 0

    for v_name, r_dict in data_output["venues"].items():
        for r_key, r_val in r_dict.items():
            res = r_val["result"]
            if res:
                finished_cnt += 1
                pay = r_val["payout"]
                if res == r_val["honmei"]:
                    h_cnt += 1
                    total_pay += pay
                elif res == r_val["chuan"]:
                    c_cnt += 1
                    total_pay += pay
                elif res == r_val["oana"]:
                    o_cnt += 1
                    total_pay += pay

    total_races = data_output["total_races"]
    total_hits = h_cnt + c_cnt + o_cnt
    invest = finished_cnt * 200
    hit_rate = f"{(total_hits / total_races * 100):.1f}%" if total_races > 0 else "0.0%"
    recovery = f"{(total_pay / invest * 100):.1f}%" if invest > 0 else "0.0%"

    if finished_cnt > 0:
        history_data[today_str] = {
            "date": today_str,
            "finished": total_races,
            "hits": total_hits,
            "hCnt": h_cnt,
            "cCnt": c_cnt,
            "oCnt": o_cnt,
            "hitRate": hit_rate,
            "totalPay": total_pay,
            "recovery": recovery,
            "invest": invest
        }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data_output, f, ensure_ascii=False, indent=2)

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    print("Completed successfully.")

if __name__ == "__main__":
    main()
