from browser import create_driver
from auth import login
from poller import start_polling
from selenium.webdriver.support.ui import WebDriverWait

def main():
    driver = create_driver()
    wait = WebDriverWait(driver, 20)

    login(driver, wait)
    start_polling(driver, interval=30)


if __name__ == "__main__":
    main()
