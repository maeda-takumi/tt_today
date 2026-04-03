import requests

BASE_URL = "https://totalappworks.com/timetree/api"


def get_pending_request():
    try:
        res = requests.get(
            f"{BASE_URL}/get_scrape_request.php",
            timeout=10
        )

        if res.status_code != 200:
            print(f"⚠ API HTTPエラー: {res.status_code}")
            return None

        if not res.text.strip():
            return None

        return res.json()

    except Exception as e:
        print(f"⚠ get_pending_request エラー: {e}")
        return None


# ==========================
# ★ JSON で送る（超重要）
# ==========================
def lock_request(req_id):
    try:
        res = requests.post(
            f"{BASE_URL}/lock_scrape_request.php",
            json={"id": req_id},  # ★ ここが重要
            timeout=10
        )

        if res.status_code != 200 or not res.text.strip():
            print("⚠ lock_request レスポンス異常")
            print(res.text)
            return None

        return res.json()

    except Exception as e:
        print(f"⚠ lock_request エラー: {e}")
        return None


def finish_request(req_id, status="done", error_message=None):
    try:
        res = requests.post(
            f"{BASE_URL}/finish_scrape_request.php",
            json={
                "id": req_id,
                "status": status,
                "message": error_message
            },
            timeout=10
        )

        if res.status_code != 200:
            print("⚠ finish_request HTTPエラー", res.status_code)

    except Exception as e:
        print(f"⚠ finish_request エラー: {e}")
