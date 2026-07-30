"""Source-tree entry point for direct Hermes plugin installs.

The distributable Python package lives in ``hybrid_contextual_routing``.
Keeping this thin wrapper at the repository root also makes
``hermes plugins install smfworks/hermes-plugin-hybrid-routing`` work.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hybrid_contextual_routing import register
elif __package__:
    from .hybrid_contextual_routing import register
else:
    from hybrid_contextual_routing import register

__all__ = ["register"]
