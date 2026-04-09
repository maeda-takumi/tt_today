from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]
SHEET_NAME = "データ"
logger = logging.getLogger(__name__)


def _to_yyyy_mm_dd(date_str: str) -> str:
    # "2026-04-03" -> "2026/04/03"
    return (date_str or "").replace("-", "/")


def _to_hh_mm(time_str: str) -> str:
    """
    "10:00:00" -> "10:00"
    "10:00"    -> "10:00"
    "" / None  -> ""
    """
    if not time_str:
        return ""
    raw = str(time_str).strip()
    # HH:MM:SS or HH:MM
    parts = raw.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return raw


def parse_title_fields(title: str) -> tuple[str, str]:
    """
    システム名: 最初の開きカッコより左
    LINE名    : 最初の対応カッコ内
    半角/全角 両対応
    取れなければ ("", "")
    """
    if not title:
        return "", ""

    t = str(title).strip()

    # 最初に出る開きカッコ（半角/全角）を検出
    open_idx = -1
    open_ch = ""
    for ch in ("(", "（"):
        i = t.find(ch)
        if i != -1 and (open_idx == -1 or i < open_idx):
            open_idx = i
            open_ch = ch

    if open_idx == -1:
        return "", ""

    close_ch = ")" if open_ch == "(" else "）"
    close_idx = t.find(close_ch, open_idx + 1)
    if close_idx == -1:
        return "", ""

    system_name = t[:open_idx].strip()
    line_name = t[open_idx + 1 : close_idx].strip()

    if not system_name or not line_name:
        return "", ""

    return system_name, line_name


def _build_row(user_name: str, event_date: str, start_time: str, end_time: str, title: str) -> list[str]:
    system_name, line_name = parse_title_fields(title)
    return [
        user_name or "",               # A: セールス名
        _to_yyyy_mm_dd(event_date),    # B: 予定日
        _to_hh_mm(start_time),         # C: 開始時間
        _to_hh_mm(end_time),           # D: 終了時間
        title or "",                   # E: タイトル
        system_name,                   # F: システム名
        line_name,                     # G: LINE名
        "",                            # H: メモ
    ]


def _create_gspread_client(service_account_json_path: Path):
    creds = Credentials.from_service_account_file(str(service_account_json_path), scopes=SCOPES)
    return gspread.authorize(creds)


def _load_spid_to_name(user_json_path: Path) -> dict[str, str]:
    data = json.loads(user_json_path.read_text(encoding="utf-8"))
    users = data.get("users", [])
    result: dict[str, str] = {}
    for u in users:
        sp_id = str(u.get("sp_id", "")).strip()
        name = str(u.get("name", "")).strip()
        if sp_id:
            result[sp_id] = name
    return result


def export_events_to_sheets(
    db_path: Path,
    user_json_path: Path,
    event_date: str,
    service_account_json_path: Path | None = None,
) -> dict:
    """
    event_date: "YYYY-MM-DD"
    同一sp_id内は start_time 昇順で出力
    """
    spid_to_name = _load_spid_to_name(user_json_path)

    # スプシ書き込み時の認証情報は ui.py と同階層の service_account.json を既定利用
    default_service_account_path = Path(__file__).resolve().with_name("service_account.json")
    credentials_path = service_account_json_path or default_service_account_path

    if not credentials_path.exists():
        raise FileNotFoundError(f"service_account.json が見つかりません: {credentials_path}")

    client = _create_gspread_client(credentials_path)

    write_errors: list[dict[str, str]] = []
    updated_count = 0

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row

        for sp_id, user_name in spid_to_name.items():
            rows = conn.execute(
                """
                SELECT user_name, event_date, start_time, end_time, title,detail
                FROM events
                WHERE event_date = ? AND sp_id = ?
                ORDER BY start_time ASC
                """,
                (event_date, sp_id),
            ).fetchall()

            values = [
                _build_row(
                    user_name=(r["user_name"] or user_name),
                    event_date=r["event_date"],
                    start_time=r["end_time"],
                    end_time=r["detail"],
                    title=r["title"],
                )
                for r in rows
            ]

            try:
                sh = client.open_by_key(sp_id)
                ws = sh.worksheet(SHEET_NAME)

                # 2行目以降を全消し
                ws.batch_clear(["A2:H"])

                # データがあるときだけ書き込み
                if values:
                    ws.update("A2:H", values, value_input_option="RAW")
                updated_count += 1
            except PermissionError:
                write_errors.append(
                    {
                        "sp_id": sp_id,
                        "user_name": user_name,
                        "reason": (
                            "service_account.json の client_email に対象スプレッドシートの閲覧/編集権限がありません。"
                        ),
                    }
                )
            except APIError as ex:
                error_reason = str(ex)
                if "403" in error_reason:
                    write_errors.append(
                        {
                            "sp_id": sp_id,
                            "user_name": user_name,
                            "reason": (
                                "Google Sheets API 403: service_account.json の client_email に対象シートの権限が必要です。"
                            ),
                        }
                    )
                else:
                    raise

    if write_errors:
        for err in write_errors:
            logger.warning(
                "シート書き込みスキップ: user=%s sp_id=%s reason=%s",
                err["user_name"],
                err["sp_id"],
                err["reason"],
            )

    return {
        "ok": len(write_errors) == 0,
        "updated_count": updated_count,
        "error_count": len(write_errors),
        "errors": write_errors,
        "message": "sheet export done",
    }
