from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from sheet_writer import export_events_to_sheets
@dataclass
class TargetUser:
    name: str
    tree_id: str
    sp_id: str


BASE_DIR = Path(__file__).resolve().parent
USER_JSON_PATH = BASE_DIR / "user.json"
DB_PATH = BASE_DIR / "events.db"
SERVICE_ACCOUNT_JSON_PATH = BASE_DIR / "service_account.json"

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

def load_targets(path: Path = USER_JSON_PATH) -> list[TargetUser]:
    data = json.loads(path.read_text(encoding="utf-8"))
    users = data.get("users", [])
    targets: list[TargetUser] = []
    for row in users:
        name = str(row.get("name", "")).strip()
        tree_id = str(row.get("tree_id", "")).strip()
        sp_id = str(row.get("sp_id", "")).strip()
        if name and tree_id and sp_id:
            targets.append(TargetUser(name=name, tree_id=tree_id, sp_id=sp_id))
    return targets


def init_db(path: Path = DB_PATH) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS events")
        conn.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                tree_id TEXT NOT NULL,
                sp_id TEXT NOT NULL,
                event_date TEXT NOT NULL,
                title TEXT,
                start_time TEXT,
                end_time TEXT,
                detail TEXT,
                event_url TEXT,
                scraped_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _create_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=ja-JP")
    return webdriver.Chrome(options=options)


def _login(driver, wait: WebDriverWait) -> None:
    email = "jiangqiantian54@gmail.com"
    password = "maedamaeda0612"

    driver.get("https://timetreeapp.com/signin")

    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys(email)

    password_input = driver.find_element(By.NAME, "password")
    password_input.clear()
    password_input.send_keys(password)
    password_input.send_keys(Keys.ENTER)

    wait.until(EC.url_contains("/calendars/"))


def _extract_events_from_daily(driver, target: TargetUser, today_str: str) -> list[dict]:
    daily_url = f"https://timetreeapp.com/calendars/{target.tree_id}/daily/{today_str}"
    logger.info("日次ページへアクセス: user=%s tree_id=%s url=%s", target.name, target.tree_id, daily_url)
    driver.get(daily_url)

    anchors = _wait_for_event_anchors_settled(driver, today_str)

    logger.info("候補イベント取得: user=%s date=%s anchor_count=%s", target.name, today_str, len(anchors))

    events: list[dict] = []
    if not anchors:
        return events

    for a_tag in anchors:
        href = a_tag.get_attribute("href") or ""

        title = ""
        h_tags = a_tag.find_elements(By.TAG_NAME, "h3")
        if h_tags:
            title = h_tags[0].text.strip()

        text_blocks = [d.text.strip() for d in a_tag.find_elements(By.TAG_NAME, "div") if d.text.strip()]
        start_time = text_blocks[0] if len(text_blocks) >= 1 else ""
        end_time = text_blocks[1] if len(text_blocks) >= 2 else ""
        detail = text_blocks[2] if len(text_blocks) >= 3 else ""

        events.append(
            {
                "user_name": target.name,
                "tree_id": target.tree_id,
                "sp_id": target.sp_id,
                "event_date": today_str,
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "detail": detail,
                "event_url": href,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    return events


def _wait_for_event_anchors_settled(
    driver,
    date_str: str,
    timeout: float = 12.0,
    poll_interval: float = 0.4,
) -> list:
    specific_selector = (By.CSS_SELECTOR, f'ul[data-date="{date_str}"]')
    fallback_selectors = [
        specific_selector,
        (By.CSS_SELECTOR, "ul[data-date]"),
        (By.CSS_SELECTOR, "main"),
    ]

    try:
        WebDriverWait(driver, 20).until(
            lambda d: any(d.find_elements(*selector) for selector in fallback_selectors)
        )
    except TimeoutException:
        logger.warning("イベントコンテナ待機タイムアウト: date=%s", date_str)
        return []

    started_at = time.time()
    prev_count = -1
    stable_hits = 0
    latest_anchors = []

    while time.time() - started_at < timeout:
        try:
            containers = driver.find_elements(*specific_selector)
            if containers:
                latest_anchors = containers[0].find_elements(By.TAG_NAME, "a")
            else:
                # data-date が見つからないページ構造でも、日次イベントリンクを回収できるようにする
                latest_anchors = driver.find_elements(By.CSS_SELECTOR, 'main a[href*="/events/"]')
            count = len(latest_anchors)
        except (NoSuchElementException, StaleElementReferenceException):
            prev_count = -1
            stable_hits = 0
            time.sleep(poll_interval)
            continue

        if count == prev_count:
            stable_hits += 1
        else:
            stable_hits = 0
            prev_count = count

        if stable_hits >= 2:
            return latest_anchors

        time.sleep(poll_interval)

    return latest_anchors

def _save_events(events: list[dict], path: Path = DB_PATH) -> int:
    if not events:
        return 0

    sql = """
    INSERT INTO events (
        user_name, tree_id, sp_id, event_date, title,
        start_time, end_time, detail, event_url, scraped_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    rows = [
        (
            e["user_name"],
            e["tree_id"],
            e["sp_id"],
            e["event_date"],
            e["title"],
            e["start_time"],
            e["end_time"],
            e["detail"],
            e["event_url"],
            e["scraped_at"],
        )
        for e in events
    ]

    with sqlite3.connect(path) as conn:
        conn.executemany(sql, rows)
        conn.commit()

    return len(rows)


def run_daily_scraping() -> dict:
    targets = load_targets()
    init_db()

    logger.info("スクレイピング開始: target_count=%s", len(targets))
    if not targets:
        return {"ok": False, "saved_count": 0, "message": "user.json の users が空です。"}

    today_str = date.today().isoformat()
    driver = _create_driver()
    wait = WebDriverWait(driver, 20)

    try:
        # 実行毎に1回ログイン
        _login(driver, wait)
        events = []
        no_event_users = []
        for target in targets:
            try:
                user_events = _extract_events_from_daily(driver, target, today_str)
                if user_events:
                    events.extend(user_events)
                    logger.info("イベント取得成功: user=%s date=%s count=%s", target.name, today_str, len(user_events))
                else:
                    no_event_users.append(target.name)
                    logger.info("イベントなし: user=%s date=%s", target.name, today_str)
            except Exception:
                logger.exception("ユーザー処理失敗: user=%s tree_id=%s", target.name, target.tree_id)
                no_event_users.append(target.name)

        saved_count = _save_events(events)

        try:
            export_events_to_sheets(
                db_path=DB_PATH,
                user_json_path=USER_JSON_PATH,
                event_date=today_str,  # YYYY-MM-DD
                service_account_json_path=SERVICE_ACCOUNT_JSON_PATH,
            )
            logger.info("スプレッドシート反映完了: date=%s", today_str)
        except Exception:
            logger.exception("スプレッドシート反映失敗: date=%s", today_str)

        logger.info(
            "スクレイピング終了: saved_count=%s target_count=%s no_event_count=%s",
            saved_count,
            len(targets),
            len(no_event_users),
        )
        return {
            "ok": True,
            "saved_count": saved_count,
            "target_count": len(targets),
            "event_date": today_str,
            "message": f"{saved_count}件を保存しました。（対象{len(targets)}件 / 予定なし{len(no_event_users)}件）",
        }
    finally:
        driver.quit()
