import re
import sys
import threading
import tkinter as tk
from pathlib import Path
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

from selenium.webdriver.support.ui import WebDriverWait

from sample.auth import login
from sample.browser import create_driver
from sample.scraper import scrape_events
from sample.sheets import sync_event_dates_to_sheet
from sample.storage import DB_PATH, export_events_to_csv, get_connection, init_db, save_events

GREEN = "#22c55e"
GREEN_DARK = "#15803d"
BG = "#f8fafc"
CARD = "#ffffff"
TEXT = "#0f172a"
MUTED = "#64748b"

SPREADSHEET_ID = "1mDccfeN9sR8OJdWLv6wPN0DzRr5Y5OfLSmrjjHOvMIs"
SPREADSHEET_SHEET_NAME = "ChatGPT"

# def get_credentials_path() -> Path:
#     """credentials.json の参照先を実行形態に応じて解決する。"""
#     if getattr(sys, "frozen", False):
#         return Path(sys.executable).resolve().parent / "credentials.json"
#     return Path(__file__).resolve().with_name("credentials.json")


# CREDENTIALS_PATH = get_credentials_path()

CREDENTIALS_PATH = "credentials.json"
def resource_path(relative_path: str) -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_dir / relative_path

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TimeTree Polling Scraper")
        self.root.geometry("900x660")
        self.root.configure(bg=BG)
        self._icon_image = None
        self._set_window_icon()

        self.status = tk.StringVar(value="待機中")
        self.poll_time = tk.StringVar(value="09:00")
        self.keyword = tk.StringVar(value="")
        self.db_path = tk.StringVar(value=str(DB_PATH))
        self.csv_path = tk.StringVar(value="events_export.csv")

        self.poll_after_id = None
        self.is_running = False

        self._setup_style()
        self._build()

    def _set_window_icon(self):
        ico_path = resource_path("img/icon.ico")
        png_path = resource_path("img/icon.png")

        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
            except Exception:
                pass

        if png_path.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self._icon_image)
            except Exception:
                pass
    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED)
        style.configure("CardLabel.TLabel", background=CARD, foreground=TEXT)
        style.configure("TEntry", padding=6)
        style.configure("Accent.TButton", background=GREEN, foreground="white", padding=(16, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", GREEN_DARK)])
        style.configure("Ghost.TButton", background="#e2e8f0", foreground=TEXT, padding=(14, 8), borderwidth=0)

    def _build(self):
        wrap = ttk.Frame(self.root, padding=24)
        wrap.pack(fill="both", expand=True)

        ttk.Label(wrap, text="TimeTree Polling Scraper", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            wrap,
            text="全カレンダー対象 / 実行時点の前日を取得 / 日次ポーリング / SQLite + CSV",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(4, 18))

        card = ttk.Frame(wrap, style="Card.TFrame", padding=20)
        card.pack(fill="x")

        self._field(card, 0, "ポーリング時刻 (HH:MM)", self.poll_time)
        self._field(card, 1, "キーワード（任意）", self.keyword)
        self._field(card, 2, "DBファイル", self.db_path)
        self._field(card, 3, "CSV出力ファイル", self.csv_path)

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        ttk.Button(buttons, text="ポーリング開始/更新", style="Ghost.TButton", command=self.update_poll_schedule).grid(
            row=0, column=0, padx=(0, 8)
        )
        self.scrape_btn = ttk.Button(buttons, text="スクレイピング実行", style="Accent.TButton", command=self.start_scrape)
        self.scrape_btn.grid(row=0, column=1, padx=8)
        ttk.Button(buttons, text="CSV出力", style="Ghost.TButton", command=self.export_csv).grid(row=0, column=2, padx=8)
        ttk.Button(buttons, text="保存先選択", style="Ghost.TButton", command=self.select_csv).grid(row=0, column=3, padx=8)

        status_wrap = ttk.Frame(wrap)
        status_wrap.pack(fill="x", pady=(16, 0))
        ttk.Label(status_wrap, text="Status:", style="Sub.TLabel").pack(side="left")
        ttk.Label(status_wrap, textvariable=self.status).pack(side="left", padx=(8, 0))

        self.log = tk.Text(wrap, height=18, bg="#0b1220", fg="#d1fae5", font=("Consolas", 10), relief="flat")
        self.log.pack(fill="both", expand=True, pady=(10, 0))

    def _field(self, parent, row: int, label: str, var: tk.StringVar):
        ttk.Label(parent, text=label, style="CardLabel.TLabel").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=var, width=70).grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=8)
        parent.columnconfigure(1, weight=1)

    def _append_log(self, msg: str):
        self.log.insert("end", f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        self.log.see("end")

    def _validate_poll_time(self, value: str) -> bool:
        return re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", value or "") is not None

    def update_poll_schedule(self):
        t = self.poll_time.get().strip()
        if not self._validate_poll_time(t):
            messagebox.showerror("Error", "時刻は HH:MM 形式で入力してください（例: 09:00）")
            return
        self.schedule_next_poll()
        self._append_log(f"ポーリング時刻を更新: {t}")

    def schedule_next_poll(self):
        if self.poll_after_id is not None:
            try:
                self.root.after_cancel(self.poll_after_id)
            except Exception:
                pass
            self.poll_after_id = None

        hh, mm = map(int, self.poll_time.get().split(":"))
        now = datetime.now()
        next_run = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        delay_ms = int((next_run - now).total_seconds() * 1000)
        self.poll_after_id = self.root.after(delay_ms, self.on_poll_trigger)
        self._append_log(f"次回ポーリング予定: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

    def on_poll_trigger(self):
        self._append_log("定時ポーリング時刻になりました")
        self.start_scrape(trigger="polling")
        self.schedule_next_poll()

    def select_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.csv_path.set(path)

    def start_scrape(self, trigger: str = "manual"):
        if self.is_running:
            self._append_log(f"実行中のためスキップ（trigger={trigger}）")
            return

        self.is_running = True
        self.scrape_btn.state(["disabled"])
        threading.Thread(target=self._run_scrape, args=(trigger,), daemon=True).start()

    def _run_scrape(self, trigger: str):
        try:
            keyword = self.keyword.get().strip()
            db_path = self.db_path.get().strip() or str(DB_PATH)

            executed_at = datetime.now()
            # target_date = executed_at.date() - timedelta(days=1)
            target_date = executed_at.date()

            self.root.after(0, self.status.set, "ログイン中...")
            self.root.after(
                0,
                self._append_log,
                f"実行開始(trigger={trigger}) 実行日時={executed_at.strftime('%Y-%m-%d %H:%M:%S')} 対象日={target_date.isoformat()}",
            )

            driver = create_driver()
            try:
                login(driver, WebDriverWait(driver, 20))
                self.root.after(0, self.status.set, "取得中...")
                events = scrape_events(driver, start_date=target_date, keyword=keyword)
            finally:
                driver.quit()

            with get_connection(db_path) as conn:
                init_db(conn)
                count = save_events(conn, events)

            self.root.after(0, self._append_log, f"DB保存完了 {db_path} ({count}件)")
            def sheets_log(message: str):
                self.root.after(0, self._append_log, message)

            sync_summary = sync_event_dates_to_sheet(
                spreadsheet_id=SPREADSHEET_ID,
                sheet_name=SPREADSHEET_SHEET_NAME,
                credentials_path=CREDENTIALS_PATH,
                rows=events,
                scraped_on=executed_at.date(),
                logger=sheets_log,
            )

            self.root.after(
                0,
                self.status.set,
                f"完了: {count}件保存 / スプシ更新{sync_summary['updated']}件",
            )
        except Exception as exc:
            self.root.after(0, self.status.set, "エラー")
            self.root.after(0, self._append_log, f"エラー: {exc}")
            self.root.after(0, messagebox.showerror, "Error", str(exc))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.scrape_btn.state(["!disabled"]))

    def export_csv(self):
        try:
            # 前日固定仕様に合わせる
            target_date = datetime.now().date() - timedelta(days=1)
            end = target_date + timedelta(days=30)
            db_path = self.db_path.get().strip() or str(DB_PATH)
            csv_path = self.csv_path.get().strip() or "events_export.csv"

            with get_connection(db_path) as conn:
                init_db(conn)
                count = export_events_to_csv(
                    conn=conn,
                    output_path=csv_path,
                    start_date=target_date.isoformat(),
                    end_date=end.isoformat(),
                    keyword=self.keyword.get().strip(),
                )

            self.status.set(f"CSV出力完了: {count}件")
            self._append_log(f"CSV出力 {csv_path} ({count}件)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self._append_log(f"CSV出力失敗: {exc}")


def main():
    root = tk.Tk()
    app = App(root)
    app._append_log("アプリ起動")
    app.schedule_next_poll()  # 起動中のみ有効
    root.mainloop()


if __name__ == "__main__":
    main()