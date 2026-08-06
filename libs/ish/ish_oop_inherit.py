"""
Python port of ish.oop.inherit.js.

Provides ``ish.oop.inherit`` — prototype-style inheritance helpers. In Python
these are thin wrappers over normal class construction, kept for API parity so
ported application code can call the same entry points.
"""

from .ish import Obj, _is_plain_obj, extend


class _Inherit:
    """ish.oop.inherit"""

    @staticmethod
    def obj(base, *extensions):
        """Create a new object inheriting from base, overlaid with extensions."""
        result = extend(Obj(), base if _is_plain_obj(base) else Obj())
        for extension in extensions:
            extend(result, extension)
        return result

    @staticmethod
    def cls(base, name="Inherited", members=None):
        """Create a subclass of base with the passed members attached."""
        members = members or {}
        bases = base if isinstance(base, tuple) else (base,)
        return type(name, bases, dict(members))

    @staticmethod
    def mixin(target, *sources):
        """Copy attributes from each source onto target (a class or instance)."""
        for source in sources:
            if _is_plain_obj(source):
                for key, value in source.items():
                    setattr(target, key, value)
            else:
                for key in dir(source):
                    if not key.startswith("__"):
                        setattr(target, key, getattr(source, key))
        return target


def apply(ish):
    """Attach ``oop.inherit`` to the passed ish instance and return it."""
    if not hasattr(ish, "oop") or ish.oop is None:
        ish.oop = Obj()
    ish.oop.inherit = _Inherit
    return ish
