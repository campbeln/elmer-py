"""
ishJS — Python port.

Mirrors the JS require-and-extend load order used by Elmer's entry point:

    ish = core()
    ish_type_ex.apply(ish)
    ish_io_net.apply(ish)
    ...
"""

from .ish import Ish, Obj, core, extend, resolve, query, uuid  # noqa: F401
from . import (  # noqa: F401
    ish_io_csv,
    ish_io_net,
    ish_io_web,
    ish_oop_inherit,
    ish_oop_overload,
    ish_type_date_format,
    ish_type_enum,
    ish_type_ex,
)

__all__ = [
    "Ish", "Obj", "core", "extend", "resolve", "query", "uuid",
    "ish_type_ex", "ish_type_date_format", "ish_io_net", "ish_io_web",
    "ish_io_csv", "ish_oop_inherit", "ish_oop_overload", "ish_type_enum",
]
