from abc import ABC, abstractmethod
import logging
from typing import Type, Dict, Any

logger = logging.getLogger(__name__)

class FactoryError(Exception):
    """Exception raised for errors in the factory."""
    pass

class BaseFactory(ABC):
    """
    Abstract base class for factories.

    This class manages the registration and creation of components using a string key.
    Subclasses can inherit and extend the functionality for specific component types.
    """
    registry: Dict[str, Type[Any]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a class with the factory."""
        def decorator(cls_type: Type):
            cls.registry[name] = cls_type
            return cls_type
        return decorator

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> Any:
        """Creates an instance of a registered class."""
        if name in cls.registry:
            return cls.registry[name](**kwargs)
        raise FactoryError(f"Unknown type: '{name}'. Available types: {list(cls.registry.keys())}")
