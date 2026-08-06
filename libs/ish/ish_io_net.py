"""
Python port of ish.io.net.js.

Provides ``ish.io.net`` — a small HTTP client whose responses are normalised
into an object exposing ``.ok``, ``.status`` and ``.data``, plus the
``ish.io.net.status`` code enum that Elmer's routes return directly.

In the original this wraps node-fetch/XMLHttpRequest; here it wraps requests.
"""

import ipaddress
import json as _json

import requests

from .ish import Obj, _wrap


# ==================================================
# HTTP status enum (ish.io.net.status)
# ==================================================
STATUS = Obj({
    "informational": Obj({
        "continue": 100,
        "switchingProtocols": 101,
        "processing": 102,
    }),
    "success": Obj({
        "ok": 200,
        "created": 201,
        "accepted": 202,
        "noContent": 204,
        "partialContent": 206,
    }),
    "redirection": Obj({
        "movedPermanently": 301,
        "found": 302,
        "seeOther": 303,
        "notModified": 304,
        "temporaryRedirect": 307,
        "permanentRedirect": 308,
    }),
    "clientError": Obj({
        "badRequest": 400,
        "unauthorized": 401,
        "paymentRequired": 402,
        "forbidden": 403,
        "notFound": 404,
        "methodNotAllowed": 405,
        "notAcceptable": 406,
        "requestTimeout": 408,
        "conflict": 409,
        "gone": 410,
        "payloadTooLarge": 413,
        "uriTooLong": 414,
        "unsupportedMediaType": 415,
        "imATeapot": 418,
        "unprocessableEntity": 422,
        "tooManyRequests": 429,
    }),
    "serverError": Obj({
        "internalServerError": 500,
        "notImplemented": 501,
        "badGateway": 502,
        "serviceUnavailable": 503,
        "gatewayTimeout": 504,
    }),
})


DEFAULT_TIMEOUT = 30


def _normalise(response, url):
    """Turn a requests.Response into the shape ish.io.net callers expect."""
    data = None
    text = ""
    try:
        text = response.text
    except Exception:
        text = ""

    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type.lower():
        try:
            data = _wrap(response.json())
        except (ValueError, _json.JSONDecodeError):
            data = text
    else:
        # Elmer frequently posts/reads JSON without a strict content type,
        # so fall back to an opportunistic parse before giving up on text.
        try:
            data = _wrap(_json.loads(text))
        except (ValueError, TypeError):
            data = text

    return Obj({
        "ok": response.ok,
        "status": response.status_code,
        "statusText": response.reason or "",
        "headers": dict(response.headers),
        "url": url,
        "data": data,
        "text": text,
    })


def _failed(url, error):
    """Shape a transport-level failure the same way as an HTTP response."""
    return Obj({
        "ok": False,
        "status": 0,
        "statusText": str(error),
        "headers": {},
        "url": url,
        "data": None,
        "text": "",
        "error": str(error),
    })


def _request(method, url, body=None, options=None):
    options = options or {}
    headers = dict(options.get("headers") or {})
    content_type = options.get("contentType")
    timeout = options.get("timeout", DEFAULT_TIMEOUT)

    kwargs = {"headers": headers, "timeout": timeout}

    if body is not None:
        if content_type and "json" not in content_type.lower():
            headers.setdefault("Content-Type", content_type)
            kwargs["data"] = body
        else:
            headers.setdefault("Content-Type", "application/json")
            kwargs["json"] = body

    try:
        response = requests.request(method, url, **kwargs)
    except requests.RequestException as error:
        return _failed(url, error)

    return _normalise(response, url)


class _Ip:
    """ish.io.net.ip"""

    @staticmethod
    def is_(value):
        try:
            ipaddress.ip_address(str(value).strip())
            return True
        except (ValueError, TypeError):
            return False


class _Net:
    status = STATUS
    ip = _Ip

    @staticmethod
    def get(url, options=None):
        return _request("GET", url, None, options)

    @staticmethod
    def post(url, body=None, options=None):
        return _request("POST", url, body, options)

    @staticmethod
    def put(url, body=None, options=None):
        return _request("PUT", url, body, options)

    @staticmethod
    def delete(url, options=None):
        return _request("DELETE", url, None, options)

    @staticmethod
    def head(url, options=None):
        return _request("HEAD", url, None, options)


def apply(ish):
    """Attach ``io.net`` to the passed ish instance and return it."""
    ish.io.net = _Net
    return ish
