from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from processor import load_targets, run_daily_scraping
from style import apply_style


class PollingApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TimeTree Daily Polling")
        self.root.geometry("760x520")
        self.root.minsize(700, 500)

        apply_style(self.root)

        self.running = False
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.user_targets = load_targets()
        self.user_selection_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self.root, style="App.TFrame", padding=20)
        container.pack(fill="both", expand=True)

        card = ttk.Frame(container, style="Card.TFrame", padding=24)
        card.pack(fill="both", expand=True)

        ttk.Label(card, text="TimeTree Polling Scheduler", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="毎日指定時刻にスクレイピングを実行し、当日予定をDBへ保存します。",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 20))

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x")

        ttk.Label(form, text="実行時刻 (HH:MM)", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        self.time_var = tk.StringVar(value="09:00")
        self.time_entry = ttk.Entry(form, textvariable=self.time_var, width=12, style="App.TEntry")
        self.time_entry.grid(row=1, column=0, sticky="w", pady=(6, 0))

        ttk.Label(form, text="今すぐ実行対象ユーザ", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=(16, 0))
        users_frame = ttk.Frame(form, style="Card.TFrame")
        users_frame.grid(row=3, column=0, sticky="w", pady=(6, 0))
        for idx, target in enumerate(self.user_targets):
            var = tk.BooleanVar(value=True)
            self.user_selection_vars[target.name] = var
            ttk.Checkbutton(users_frame, text=target.name, variable=var).grid(
                row=idx // 3,
                column=idx % 3,
                sticky="w",
                padx=(0, 14),
                pady=(0, 4),
            )
        button_row = ttk.Frame(card, style="Card.TFrame")
        button_row.pack(fill="x", pady=(20, 12))

        self.start_btn = ttk.Button(button_row, text="ポーリング開始", style="App.TButton", command=self.start_polling)
        self.start_btn.pack(side="left")

        self.stop_btn = ttk.Button(button_row, text="停止", style="App.TButton", command=self.stop_polling)
        self.stop_btn.pack(side="left", padx=(10, 0))
        self.stop_btn.state(["disabled"])

        self.run_now_btn = ttk.Button(button_row, text="今すぐ実行", style="App.TButton", command=self.run_now)
        self.run_now_btn.pack(side="left", padx=(10, 0))

        self.status_var = tk.StringVar(value="停止中")
        ttk.Label(card, textvariable=self.status_var, style="Status.TLabel").pack(anchor="w", pady=(0, 8))

        ttk.Label(card, text="ログ", style="Body.TLabel").pack(anchor="w")
        self.log_box = tk.Text(
            card,
            height=16,
            bg="#FFFFFF",
            fg="#374151",
            relief="solid",
            borderwidth=1,
            insertbackground="#374151",
            highlightthickness=0,
            padx=10,
            pady=10,
        )
        self.log_box.pack(fill="both", expand=True, pady=(6, 0))
        self.log_box.configure(state="disabled")

    def log(self, message: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _parse_time(self) -> tuple[int, int]:
        raw = self.time_var.get().strip()
        try:
            hour_str, minute_str = raw.split(":")
            hour, minute = int(hour_str), int(minute_str)
        except Exception as exc:
            raise ValueError("時刻は HH:MM 形式で入力してください。") from exc

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("時刻は 00:00〜23:59 の範囲で入力してください。")
        return hour, minute

    def _next_run_at(self, hour: int, minute: int) -> datetime:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        return target

    def start_polling(self):
        if self.running:
            return

        try:
            hour, minute = self._parse_time()
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        self.running = True
        self.stop_event.clear()
        self.start_btn.state(["disabled"])
        self.stop_btn.state(["!disabled"])
        self.status_var.set("ポーリング実行中")

        self.worker = threading.Thread(target=self._poll_loop, args=(hour, minute), daemon=True)
        self.worker.start()
        self.log(f"ポーリング開始: 毎日 {hour:02d}:{minute:02d} に実行")

    def stop_polling(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running = False
        self.start_btn.state(["!disabled"])
        self.stop_btn.state(["disabled"])
        self.status_var.set("停止中")
        self.log("ポーリング停止")

    def _run_scraping_job(self, selected_user_names: list[str] | None = None):
        if selected_user_names is None:
            self.log("スクレイピング実行開始（全ユーザ）")
        else:
            self.log(f"スクレイピング実行開始（選択ユーザ: {', '.join(selected_user_names)}）")

        result = run_daily_scraping(selected_user_names=selected_user_names)
        if result.get("ok"):
            self.log(result.get("message", "完了"))
        else:
            self.log(f"エラー: {result.get('message', '不明なエラー')}")

    def _poll_loop(self, hour: int, minute: int):
        while not self.stop_event.is_set():
            run_at = self._next_run_at(hour, minute)
            self.log(f"次回実行予定: {run_at.strftime('%Y-%m-%d %H:%M:%S')}")

            while datetime.now() < run_at:
                if self.stop_event.wait(timeout=1):
                    return

            try:
                # ポーリング時は無条件で全ユーザを実行
                self._run_scraping_job(selected_user_names=None)
            except Exception as exc:
                self.log(f"実行失敗: {exc}")

    def run_now(self):
        selected_user_names = [
            name for name, var in self.user_selection_vars.items() if var.get()
        ]
        if not selected_user_names:
            messagebox.showerror("入力エラー", "今すぐ実行するユーザを1人以上選択してください。")
            return
        threading.Thread(target=self._run_scraping_job, args=(selected_user_names,), daemon=True).start()


def main():
    root = tk.Tk()
    app = PollingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
