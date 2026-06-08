"""Parser registry with decorator for registration."""
from typing import Type, Callable
from .base import OutputParser

# Global registry
_PARSERS: dict[str, Type[OutputParser]] = {}


def parser_for(module_pattern: str) -> Callable[[Type[OutputParser]], Type[OutputParser]]:
    """Decorator to register a parser for a module pattern.

    Args:
        module_pattern: Module path pattern (can use * for wildcard)

    Returns:
        Decorator function
    """
    def decorator(cls: Type[OutputParser]) -> Type[OutputParser]:
        _PARSERS[module_pattern] = cls
        return cls
    return decorator


def get_parser(module_path: str) -> OutputParser:
    """Get the appropriate parser for a module.

    Args:
        module_path: Full module path

    Returns:
        Parser instance (GenericParser if no specific parser found)
    """
    # Try exact match first
    if module_path in _PARSERS:
        return _PARSERS[module_path]()

    # Try pattern matching
    import fnmatch
    for pattern, parser_cls in _PARSERS.items():
        if fnmatch.fnmatch(module_path, pattern):
            return parser_cls()

    # Fallback to generic parser
    from .generic import GenericParser
    return GenericParser()
