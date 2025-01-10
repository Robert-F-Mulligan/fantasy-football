from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseParser(ABC):
    def __init__(self):
        self.content = None
        self.soup = None

    def set_content(self, content: str):
        """Set the content that will be parsed."""
        self.content = content
        logger.info("Content set successfully.")

    @abstractmethod
    def parse(self):
        """Parse the raw content."""
        pass

    @abstractmethod
    def extract(self, **kwargs):
        """Extract specific data from the parsed content."""
        pass
