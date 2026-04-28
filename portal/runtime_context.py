"""
Process-scoped dependency injection root.

Each OS process (API worker or Celery worker) registers one AppContainer at startup.
This is separate from request-scoped or event-scoped database session context.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from portal.container import Container

_root_container: Optional[Any] = None


def set_runtime_container(container: Any) -> None:
    """
    Register the root AppContainer for this process (API or worker).
    """
    global _root_container
    _root_container = container


def get_runtime_container() -> Optional["Container"]:
    """
    Return the process root AppContainer, or None if not registered.
    """
    return _root_container
