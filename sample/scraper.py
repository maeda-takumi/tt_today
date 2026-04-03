from datetime import date, datetime, timedelta
import time
import requests
import re
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException
)
import uuid
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
# ==========================
# API 設定
# ==========================
GET_CALENDARS_API = "https://totalappworks.com/timetree/api/get_calendars.php"
SAVE_EVENTS_API   = "https://totalappworks.com/timetree/api/save_calendar_events.php"


# ==========================
# 取得対象カレンダー取得（API）
# ==========================
def fetch_calendars_from_api():
    res = requests.get(GET_CALENDARS_API, timeout=30)
    if res.status_code != 200:
        raise RuntimeError(f"❌ calendars API エラー: {res.status_code}")

    data = res.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"❌ calendars API 失敗: {data}")

    calendars = data.get("calendars", [])
    print(f"📋 有効カレンダー数: {len(calendars)}")
    return calendars


# ==========================
# イベント数取得（waitなし）
# ==========================
def get_event_count(driver, date_str, max_retry=3):
    for attempt in range(max_retry):
        ul = wait_for_day_ul(driver, date_str, timeout=15)
        if ul is None:
            print(f"⏳ {date_str} ulが見つからない（attempt={attempt+1}）")
            continue

        try:
            divs = ul.find_elements(By.XPATH, './div')
            print(f"✅ {date_str} イベント数: {len(divs)}")
            return len(divs)
        except StaleElementReferenceException:
            print(f"♻ stale get_event_count 再試行 attempt={attempt+1}")
            time.sleep(0.3)

    # ここまで来たら本当に拾えてない
    print(f"⚠ {date_str} ul検出できず（予定なし扱いにする）")
    return 0

def wait_for_day_ul(driver, date_str, timeout=15):
    selector = (By.CSS_SELECTOR, f'ul[data-date="{date_str}"]')
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(selector)
        )
    except TimeoutException:
        return None

# ==========================
# イベント取得（index指定）
# ==========================
def extract_event_by_index(driver, date_str, index, max_retry=2):
    for attempt in range(max_retry):
        try:
            ul = driver.find_element(By.CSS_SELECTOR, f'ul[data-date="{date_str}"]')
            divs = ul.find_elements(By.XPATH, './div')

            if index >= len(divs):
                return None

            div = divs[index]
            a_tag = div.find_element(By.TAG_NAME, 'a')

            # タイトル
            title = ""
            h3 = a_tag.find_elements(By.TAG_NAME, "h3")
            if h3:
                title = h3[0].text.strip()

            # 子divテキスト
            inner_divs = a_tag.find_elements(By.TAG_NAME, 'div')
            texts = [d.text.strip() for d in inner_divs if d.text.strip()]

            # 時刻
            time_candidates = [
                t for t in texts
                if "終日" in t or any(c.isdigit() for c in t)
            ]
            time_text = time_candidates[0] if time_candidates else ""

            lines = time_text.splitlines()
            start_time = lines[0] if len(lines) >= 1 else ""
            end_time   = lines[1] if len(lines) >= 2 else ""

            # 詳細
            detail = ""
            for t in texts:
                if t not in (start_time, end_time):
                    detail = t
                    break

            actor, customer, sales = parse_title(title)

            return {
                "title": title,
                "actor_name": actor,
                "customer_name": customer,
                "sales_name": sales,
                "start_time": start_time,
                "end_time": end_time,
                "detail": detail,
                "event_url": a_tag.get_attribute("href"),
                "scraped_at": datetime.now(),
            }

        except StaleElementReferenceException:
            print(f"♻ stale 再試行 index={index} attempt={attempt+1}")
            time.sleep(0.3)

        except NoSuchElementException:
            return None

    print(f"⚠ index={index} 取得失敗")
    return None

def nudge_scroll(driver):
    driver.execute_script("window.scrollTo(0, 200);")
    time.sleep(0.2)
    driver.execute_script("window.scrollTo(0, 0);")
# ==========================
# イベント保存（API）
# ==========================

def send_events_to_api(events, scopes):
    sync_run_id = uuid.uuid4().hex

    payload = {
        "sync_run_id": sync_run_id,
        "scopes": scopes,   # ★これが削除反映に必須
        "events": [
            {**e, "scraped_at": e["scraped_at"].strftime("%Y-%m-%d %H:%M:%S")}
            for e in events
        ]
    }

    res = requests.post(SAVE_EVENTS_API, json=payload, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"❌ save API エラー: {res.status_code} {res.text}")

    print("🌐 API保存成功:", res.json())


# ==========================
# タイトル分解
# ==========================
def parse_title(title: str):
    actor = None
    customer = None
    sales = None

    m = re.match(r'^(.*?)[\(\（](.*?)[\)\）](.*)$', title)
    if m:
        actor = m.group(1).strip()
        customer = m.group(2).strip()
        sales = m.group(3).strip()
    else:
        actor = title.strip()

    return actor, customer, sales


# ==========================
# メイン処理（今日〜7日）
# ==========================
def scrape_events(driver):
    base_date = date.today()
    print(f"📅 取得期間: {base_date} 〜 {base_date + timedelta(days=6)}")
    scopes = []
    all_events = []
    calendars = fetch_calendars_from_api()

    for cal in calendars:
        name = cal["name"]
        calendar_id = cal["timetree_calendar_id"]

        for i in range(7):
            target_date = base_date + timedelta(days=i)
            date_str = target_date.isoformat()

            # ★ scopeは必ず追加（予定0件でも）
            scopes.append({
                "calendar_id": calendar_id,
                "event_date": date_str
            })
            url = f"https://timetreeapp.com/calendars/{calendar_id}/daily/{date_str}"
            print(f"▶ {name} / {date_str}")
            print(f"   {url}")

            driver.get(url)

            nudge_scroll(driver)  # optional だが効くことがある

            count = get_event_count(driver, date_str)  # 内部でwaitする版に差し替え

            day_events = []
            for idx in range(count):
                info = extract_event_by_index(driver, date_str, idx)
                if info:
                    info["calendar_id"]   = calendar_id
                    info["calendar_name"] = name
                    info["date"]          = date_str
                    day_events.append(info)

            all_events.extend(day_events)

    print(f"==== 取得件数: {len(all_events)} ====")
    send_events_to_api(all_events, scopes)

    print("✅ 全員分・7日間の予定取得＆API保存完了")
    return all_events
