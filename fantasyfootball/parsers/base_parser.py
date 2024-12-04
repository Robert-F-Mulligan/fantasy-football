from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseParser(ABC):
    def __init__(self, content: str):
        self.content = content

    @abstractmethod
    def parse(self):
        """Parse the raw content."""
        pass

    @abstractmethod
    def extract(self, **kwargs):
        """Extract specific data from the parsed content."""
        pass
