"""
Python port of ish.type.enum.js.

Provides ``ish.type.enum`` — bidirectional name/value lookup over a plain
mapping, used by Elmer for things like ``app.enums.userTypes``.
"""

from .ish import Obj, _is_plain_obj


class Enum:
    """A simple bidirectional enum wrapper."""

    def __init__(self, entries=None):
        self._by_name = Obj()
        self._by_value = {}
        for name, value in (entries or {}).items():
            self._by_name[name] = value
            self._by_value[value] = name

    def __getattr__(self, name):
        try:
            return self.__dict__["_by_name"][name]
        except KeyError:
            raise AttributeError(name)

    def __getitem__(self, name):
        return self._by_name[name]

    def __contains__(self, name):
        return name in self._by_name

    def name(self, value, default=None):
        """Look up the name for a value."""
        return self._by_value.get(value, default)

    def value(self, name, default=None):
        """Look up the value for a name."""
        return self._by_name.get(name, default)

    def names(self):
        return list(self._by_name.keys())

    def values(self):
        return list(self._by_name.values())

    def to_obj(self):
        return Obj(self._by_name)


class _EnumFactory:
    """ish.type.enum"""

    @staticmethod
    def mk(entries=None):
        return Enum(entries if _is_plain_obj(entries) else {})

    @staticmethod
    def is_(value):
        return isinstance(value, Enum)


def apply(ish):
    """Attach ``type.enum`` to the passed ish instance and return it."""
    ish.type.enum = _EnumFactory
    return ish
