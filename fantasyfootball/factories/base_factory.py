"""Lazy registry factories: optional integrations load only when requested."""
from importlib import import_module


class FactoryError(ValueError):
    pass


class BaseFactory:
    registry = {}
    modules = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.registry = {}

    @classmethod
    def register(cls, name):
        def decorator(component):
            existing = cls.registry.get(name)
            if existing is not None and existing is not component:
                raise FactoryError(f'Duplicate registration: {name}')
            cls.registry[name] = component
            return component
        return decorator

    @classmethod
    def create(cls, name, **kwargs):
        if name not in cls.registry and name in cls.modules:
            try:
                import_module(cls.modules[name])
            except ImportError as exc:
                raise FactoryError(f'Cannot load {name}; install its optional dependencies: {exc}') from exc
        if name not in cls.registry:
            raise FactoryError(f'Unknown type {name!r}. Available: {sorted(set(cls.registry) | set(cls.modules))}')
        return cls.registry[name](**kwargs)
