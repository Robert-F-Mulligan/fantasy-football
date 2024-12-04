from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseConnector(ABC):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")  # Ensure no trailing slash

    def construct_url(self, endpoint: str) -> str:
        """Combine base_url with endpoint."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    @abstractmethod
    def fetch(self, endpoint: str) -> str:
        """Fetch the raw HTML content of a page."""
        pass
