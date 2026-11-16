"""Serialize chained exceptions into a flat, machine-readable list.

See :mod:`exception_chain_serializer.core` for the implementation.
"""

from .core import serialize_exception_chain, SerializedException

__all__ = ["serialize_exception_chain", "SerializedException"]
