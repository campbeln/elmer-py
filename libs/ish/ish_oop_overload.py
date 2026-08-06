"""
Python port of ish.oop.overload.js.

Provides ``ish.oop.overload`` — dispatch a call to one of several
implementations based on the shape of the arguments, mimicking the JS habit of
branching on ``arguments.length`` and argument types.
"""

from .ish import Obj


class _Overload:
    """ish.oop.overload"""

    @staticmethod
    def create(default=None):
        """Build an overloaded callable.

        Register implementations by arity via ``.add(count, fn)``; calling the
        returned object dispatches on ``len(args)``, falling back to default.
        """
        registry = {}

        def dispatch(*args, **kwargs):
            handler = registry.get(len(args), default)
            if not callable(handler):
                raise TypeError(
                    "No overload registered for %d argument(s)" % len(args)
                )
            return handler(*args, **kwargs)

        def add(arg_count, fn):
            registry[arg_count] = fn
            return dispatch

        dispatch.add = add
        dispatch.registry = registry
        dispatch.default = default
        return dispatch

    @staticmethod
    def resolve(registry, args):
        """Pick the implementation matching the passed argument list."""
        return registry.get(len(args))


def apply(ish):
    """Attach ``oop.overload`` to the passed ish instance and return it."""
    if not hasattr(ish, "oop") or ish.oop is None:
        ish.oop = Obj()
    ish.oop.overload = _Overload
    return ish
