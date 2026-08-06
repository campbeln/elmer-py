"""
Python port of ish.type-ex.js.

The JS build ships the extended type helpers (``date.ydhms``,
``date.utcToLocalOffset``, ``date.cmp``, ``date.diff``, ``is.truthy``,
``str.cmp``) as a separate file layered onto the core at require-time.

In this port those implementations live alongside the rest of the type system
in ``ish.py`` for cohesion, so this module's job is to verify the extended
surface is present and expose it under the names the application expects. The
call site in ``_index.py`` is preserved so the load order matches the original.
"""

_EXPECTED = (
    ("date", ("ydhms", "utc_to_local_offset", "cmp", "diff")),
    ("str", ("cmp",)),
    ("is_", ("truthy",)),
)


def apply(ish):
    """Verify and expose the extended type surface; returns the ish instance."""
    for namespace, members in _EXPECTED:
        target = getattr(ish.type, namespace, None)
        if target is None:
            raise RuntimeError("ish.type.%s is missing; core failed to load" % namespace)
        for member in members:
            if not hasattr(target, member):
                raise RuntimeError(
                    "ish.type.%s.%s is missing; type-ex cannot be applied"
                    % (namespace, member)
                )

    # JS-style alias so ported code can read the way the original did.
    #     NOTE: ish.type.is cannot be aliased without the trailing underscore,
    #     as `is` is a reserved keyword in Python. Callers use `type.is_`.
    ish.type.date.utcToLocalOffset = ish.type.date.utc_to_local_offset
    return ish
