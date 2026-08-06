"""
Python port of ish.type.date-format.js.

Adds token-based date formatting (``YYYY-MM-DD HH:mm:ss``) to the type system.
As with type-ex, the implementation lives in ``ish.py``; this module wires it
up and registers the named format presets Elmer uses.
"""

from .ish import Obj

FORMATS = Obj({
    "iso": "YYYY-MM-DDTHH:mm:ss",
    "date": "YYYY-MM-DD",
    "time": "HH:mm:ss",
    "datetime": "YYYY-MM-DD HH:mm:ss",
    "slashed": "YYYY/MM/DD hh:mm:ss",
    "long": "DDDD, MMMM DD, YYYY",
})


def apply(ish):
    """Verify ``type.date.format`` is available and attach the presets."""
    if not hasattr(ish.type.date, "format"):
        raise RuntimeError("ish.type.date.format is missing; core failed to load")
    ish.type.date.formats = FORMATS
    return ish
