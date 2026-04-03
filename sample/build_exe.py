"""PyInstaller build script for Windows .exe packaging.

Usage:
    pip install pyinstaller
    python build_exe.py
"""

from __future__ import annotations

import os
from pathlib import Path

import PyInstaller.__main__


BASE_DIR = Path(__file__).resolve().parent
APP_FILE = BASE_DIR / "polling_app.py"
ICON_ICO = BASE_DIR / "img" / "icon.ico"
IMG_DIR = BASE_DIR / "img"


def main() -> None:
    add_data_arg = f"{IMG_DIR}{os.pathsep}img"

    PyInstaller.__main__.run(
        [
            str(APP_FILE),
            "--name=TimeTreePolling",
            "--onefile",
            "--windowed",  # no console window
            "--noconfirm",
            "--clean",
            "--hidden-import=selenium.webdriver.chrome.options",
            "--hidden-import=selenium.webdriver.chrome.webdriver",
            f"--icon={ICON_ICO}",
            f"--add-data={add_data_arg}",
        ]
    )


if __name__ == "__main__":
    main()
