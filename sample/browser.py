from selenium import webdriver


def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=ja-JP")

    driver = webdriver.Chrome(options=options)
    return driver
