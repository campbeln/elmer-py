"""
Python port of ish.io.web.js.

Provides ``ish.io.web.queryString`` — the parser Elmer uses to read query
parameters off a raw request URL (rather than trusting framework parsing).
"""

from urllib.parse import parse_qsl, urlencode, urlsplit

from .ish import Obj


class _QueryString:
    """ish.io.web.queryString"""

    @staticmethod
    def parse(url=None):
        """Parse a URL's query component into an object.

        Repeated keys collapse into a list, matching the JS implementation.
        Values are returned as strings; callers coerce via ``type.bool.mk`` etc.
        """
        if not isinstance(url, str) or not url:
            return Obj()

        query = urlsplit(url).query
        if not query and "=" in url and "?" not in url:
            # Tolerate being handed a bare "a=1&b=2" fragment.
            query = url

        result = Obj()
        for key, value in parse_qsl(query, keep_blank_values=True):
            if key in result:
                existing = result[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    result[key] = [existing, value]
            else:
                result[key] = value
        return result

    @staticmethod
    def stringify(data=None):
        """Serialise an object back into a query string."""
        if not isinstance(data, dict) or not data:
            return ""
        pairs = []
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                pairs.extend((key, item) for item in value)
            else:
                pairs.append((key, value))
        return urlencode(pairs)

    @staticmethod
    def get(url, key, default=None):
        return _QueryString.parse(url).get(key, default)


class _Web:
    queryString = _QueryString


def apply(ish):
    """Attach ``io.web`` to the passed ish instance and return it."""
    ish.io.web = _Web
    return ish
