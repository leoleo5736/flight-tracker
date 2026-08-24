# -*- coding: utf-8 -*-
"""
每日抓取長榮航空 台北(TPE) <-> 西雅圖(SEA) 【來回票】價格

用法:
    python scrape.py

輸出:
    1. prices.csv        - 每次抓到的價格都會多加幾行(不會覆蓋舊資料)
    2. 螢幕上印出當日摘要
    3. 若有設定 SHEET_WEBAPP_URL 環境變數, 會同時寫進 Google 試算表

【注意】這裡抓的是「來回票總價」, 不是兩張單程票相加。
航空公司賣來回票是一個獨立的票價, 通常比兩張單程票便宜很多。
Google Flights 的來回搜尋結果會列出「去程有哪幾班」, 每一班標的價格
就是「選這班去程的來回總價」。回程要選哪一班是下一步才決定的,
所以這支程式記錄的是: 每一個去程航班各自對應的來回總價。

要改航班/日期, 只要改下面 SETTINGS 這一段就好, 其他都不用動。
"""

import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# SETTINGS: 你只需要改這一段
# ---------------------------------------------------------------------------

# 去程
OUTBOUND_DATE = "2026-10-08"
OUTBOUND_FROM = "TPE"
OUTBOUND_TO = "SEA"

# 回程
RETURN_DATE = "2026-10-18"
RETURN_FROM = "SEA"
RETURN_TO = "TPE"

AIRLINE = "BR"          # 長榮
MAX_STOPS = 0           # 只要直飛
ADULTS = 1              # 幾個大人(價格是"每人"的價格)
CURRENCY = "TWD"

# 起飛時間 -> 航班號 對照表
FLIGHT_LABELS = {
    ("TPE", "SEA", "23:00"): "BR24",
    ("TPE", "SEA", "23:40"): "BR26",
}

# 來回總價低於這個數字就標記出來(單位: 台幣, 每人)
ALERT_BELOW = 26000

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.csv")

CSV_HEADER = [
    "抓取時間",
    "去程航班",
    "去程日期",
    "去程起飛",
    "去程抵達",
    "回程日期",
    "機型",
    "飛行分鐘",
    "來回總價TWD",
]

# ---------------------------------------------------------------------------
# 以下是程式本體, 一般不需要修改
# ---------------------------------------------------------------------------

TAIPEI = timezone(timedelta(hours=8))


def now_taipei():
    return datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M")


def fmt_date(parts):
    """[2026, 10, 8] -> '2026-10-08'"""
    return "%04d-%02d-%02d" % (parts[0], parts[1], parts[2])


def fmt_time(parts):
    """[23, 0] -> '23:00'"""
    return "%02d:%02d" % (parts[0], parts[1])


def fetch_roundtrip(attempts=3):
    """抓來回票。回傳的每一筆 = 一個去程航班 + 它對應的來回總價。"""
    from fast_flights import FlightQuery, Passengers, create_query, get_flights

    query = create_query(
        flights=[
            FlightQuery(
                date=OUTBOUND_DATE,
                from_airport=OUTBOUND_FROM,
                to_airport=OUTBOUND_TO,
                airlines=[AIRLINE],
                max_stops=MAX_STOPS,
            ),
            FlightQuery(
                date=RETURN_DATE,
                from_airport=RETURN_FROM,
                to_airport=RETURN_TO,
                airlines=[AIRLINE],
                max_stops=MAX_STOPS,
            ),
        ],
        seat="economy",
        trip="round-trip",
        passengers=Passengers(adults=ADULTS),
        language="zh-TW",
        currency=CURRENCY,
    )

    last_error = None
    for i in range(attempts):
        try:
            results = get_flights(query)
            if len(results) > 0:
                return results
            last_error = "抓到 0 筆結果"
        except Exception as exc:
            last_error = repr(exc)

        if i < attempts - 1:
            wait = 20 * (i + 1)
            print("  第 %d 次失敗 (%s), %d 秒後重試..." % (i + 1, last_error, wait))
            time.sleep(wait)

    raise RuntimeError("來回票抓取失敗: %s" % last_error)


def to_rows(results, stamp):
    """把 fast-flights 的結果整理成一行一行的資料。"""
    rows = []
    for flight in results:
        # 直飛只會有一段
        seg = flight.flights[0]
        dep_time = fmt_time(seg.departure.time)
        key = (seg.from_airport.code, seg.to_airport.code, dep_time)
        label = FLIGHT_LABELS.get(key, "未知-" + dep_time)

        rows.append(
            {
                "抓取時間": stamp,
                "去程航班": label,
                "去程日期": fmt_date(seg.departure.date),
                "去程起飛": dep_time,
                "去程抵達": fmt_date(seg.arrival.date)[5:] + " " + fmt_time(seg.arrival.time),
                "回程日期": RETURN_DATE,
                "機型": seg.plane_type,
                "飛行分鐘": seg.duration,
                "來回總價TWD": flight.price,
            }
        )
    return rows


def append_csv(rows):
    need_header = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        if need_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def push_to_sheet(rows):
    """如果有設定 Google Apps Script 網址, 就把資料也送一份過去。"""
    url = os.environ.get("SHEET_WEBAPP_URL", "").strip()
    if not url:
        return "未設定試算表網址, 略過"

    payload = {
        "token": os.environ.get("SHEET_TOKEN", ""),
        "rows": [[r[c] for c in CSV_HEADER] for r in rows],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return "試算表回應: " + resp.read().decode("utf-8", "replace")[:200]
    except Exception as exc:
        return "寫入試算表失敗: " + repr(exc)


def main():
    stamp = now_taipei()
    print("=" * 60)
    print("抓取時間:", stamp, "(台北時間)")
    print("=" * 60)

    print("\n查詢來回票: %s %s -> %s, %s %s -> %s"
          % (OUTBOUND_DATE, OUTBOUND_FROM, OUTBOUND_TO,
             RETURN_DATE, RETURN_FROM, RETURN_TO))

    rows = to_rows(fetch_roundtrip(), stamp)
    append_csv(rows)

    print("\n--- 今日來回票總價(每人) ---")
    best = None
    lines = []
    for r in rows:
        price = r["來回總價TWD"]
        mark = "  <-- 低於 %s!" % format(ALERT_BELOW, ",") if price < ALERT_BELOW else ""
        lines.append(
            "  去程 %s (%s 起飛) 來回總價 NT$%s%s"
            % (r["去程航班"], r["去程起飛"], format(price, ","), mark)
        )
        if best is None or price < best:
            best = price
    for line in lines:
        print(line)
    print("\n  最低: NT$%s" % format(best, ","))

    print("\n" + push_to_sheet(rows))
    print("已寫入:", CSV_PATH)

    # 讓 GitHub Actions 的執行摘要頁面也看得到
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## %s 最低來回總價 NT$%s\n\n" % (stamp, format(best, ",")))
            for line in lines:
                fh.write("- " + line.strip() + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("執行失敗:", repr(exc), file=sys.stderr)
        sys.exit(1)
