import time
from api_client import get_pending_request, lock_request, finish_request
from scraper import scrape_events

from browser import create_driver
from auth import login
from selenium.webdriver.support.ui import WebDriverWait


def start_polling(interval=30, on_status=None):

    while True:
        req = get_pending_request()

        # pending なし or running 中
        if not req or req.get("status") != "ok" or not req.get("request"):
            if on_status:
                on_status("idle")
            time.sleep(interval)
            continue

        request = req["request"]
        req_id = request["id"]

        if on_status:
            on_status("found", req_id)

        # ===== ロック =====
        # poller.py
        print("🔍 lock_request start")
        lock_res = lock_request(req_id)
        print("🔍 lock_request end:", lock_res)

        # ★ ロック失敗なら何もしない
        if not lock_res or not lock_res.get("locked"):
            time.sleep(interval)
            continue

        driver = None
        try:
            driver = create_driver()
            wait = WebDriverWait(driver, 20)
            login(driver, wait)

            scrape_events(driver)

            finish_request(req_id, status="done")

            if on_status:
                on_status("done")

        except Exception as e:
            finish_request(req_id, status="error", error_message=str(e))
            if on_status:
                on_status("error", str(e))

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        time.sleep(interval)

