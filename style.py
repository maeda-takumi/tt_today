from tkinter import ttk

BG_PRIMARY = "#F5F6F7"
BG_SURFACE = "#FFFFFF"
TEXT_PRIMARY = "#1F2937"
TEXT_MUTED = "#6B7280"
ACCENT = "#16A34A"
ACCENT_DARK = "#15803D"
BORDER = "#E5E7EB"


def apply_style(root):
    root.configure(bg=BG_PRIMARY)
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(
        "App.TFrame",
        background=BG_PRIMARY,
    )
    style.configure(
        "Card.TFrame",
        background=BG_SURFACE,
        bordercolor=BORDER,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "Title.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_PRIMARY,
        font=("Segoe UI", 15, "bold"),
    )
    style.configure(
        "Body.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_PRIMARY,
        font=("Segoe UI", 10),
    )
    style.configure(
        "Muted.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_MUTED,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Status.TLabel",
        background=BG_SURFACE,
        foreground=ACCENT_DARK,
        font=("Segoe UI", 10, "bold"),
    )
    style.configure(
        "App.TButton",
        background=ACCENT,
        foreground="#FFFFFF",
        borderwidth=0,
        focusthickness=3,
        focuscolor=ACCENT,
        font=("Segoe UI", 10, "bold"),
        padding=(14, 8),
    )
    style.map(
        "App.TButton",
        background=[("active", ACCENT_DARK), ("disabled", "#9CA3AF")],
        foreground=[("disabled", "#F3F4F6")],
    )
    style.configure(
        "App.TEntry",
        fieldbackground="#FFFFFF",
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        insertcolor=TEXT_PRIMARY,
        padding=(8, 6),
    )
