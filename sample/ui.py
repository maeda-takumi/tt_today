import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from poller import start_polling
from browser import create_driver
from auth import login
from selenium.webdriver.support.ui import WebDriverWait


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("TimeTree Scraper Monitor")
        self.root.geometry("520x420")

        # ===== 状態表示 =====
        self.status_label = tk.Label(
            root,
            text="未監視",
            font=("Arial", 12, "bold"),
            fg="gray"
        )
        self.status_label.pack(pady=8)

        # ===== ボタン =====
        self.start_btn = tk.Button(
            root,
            text="監視開始",
            width=20,
            command=self.start_monitor
        )
        self.start_btn.pack(pady=6)

        # ===== ログ表示 =====
        self.log_box = ScrolledText(
            root,
            height=18,
            font=("Consolas", 10)
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_box.config(state="disabled")

    # ------------------
    # ログ出力
    # ------------------
    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"{t} {msg}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # ------------------
    # 監視開始
    # ------------------
    def start_monitor(self):
        self.start_btn.config(state="disabled")
        self.status_label.config(text="起動中…", fg="orange")
        self.log("監視開始")

        t = threading.Thread(target=self.run, daemon=True)
        t.start()

    # ------------------
    # メイン処理
    # ------------------
    def run(self):
        self.status_label.config(text="監視中（30秒ポーリング）", fg="green")

        start_polling(
            interval=30,
            on_status=self.on_status
        )


    # ------------------
    # poller からの通知
    # ------------------
    def on_status(self, status, message=None):
        if status == "idle":
            self.log("フラグなし")

        elif status == "found":
            self.log(f"フラグ検知 id={message}")
            self.status_label.config(text="実行中", fg="blue")

        elif status == "done":
            self.log("スクレイピング完了")
            self.status_label.config(text="監視中（30秒ポーリング）", fg="green")

        elif status == "error":
            self.log(f"エラー: {message}")
            self.status_label.config(text="エラー", fg="red")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
