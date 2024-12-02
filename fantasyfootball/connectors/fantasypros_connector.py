from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from time import sleep
import json
import pandas as pd
import numpy as np
import re
from base_connector import BaseConnector

class FantasyProsConnector(BaseConnector):
    def __init__(self, driver_path: str):
        self.driver_path = driver_path

    def fetch_dynamic_content(self, url: str) -> str:
        """Scrape JavaScript-rendered content using Selenium."""
        options = Options()
        options.headless = True
        options.add_argument("--log-level=3")  # Suppress logs
        driver = webdriver.Chrome(options=options, executable_path=self.driver_path)
        driver.get(url)
        sleep(5)  # Allow time for the page to render
        html = driver.execute_script("return document.getElementsByTagName('html')[0].innerHTML")
        driver.quit()
        return html

    def parse_html(self, html: str) -> BeautifulSoup:
        """Override parse_html to handle dynamic HTML."""
        return super().parse_html(html)
