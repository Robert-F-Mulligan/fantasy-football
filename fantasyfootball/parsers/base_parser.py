from abc import ABC, abstractmethod
from bs4 import BeautifulSoup

class BaseParser(ABC):
    def __init__(self, soup: BeautifulSoup):
        self.soup = soup
        self.validate_soup()

    @abstractmethod
    def validate_soup(self):
        """Check if the soup is valid for this parser"""
        pass

    @abstractmethod
    def parse(self):
        pass