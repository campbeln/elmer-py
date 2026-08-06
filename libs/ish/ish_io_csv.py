"""
Python port of ish.io.csv.js.

Provides ``ish.io.csv`` — parse delimited text into a list of row objects, and
serialise a list of objects back out to delimited text.
"""

import csv as _csv
import io as _io

from .ish import Obj, _Str


class _Csv:
    """ish.io.csv"""

    @staticmethod
    def parse(text, options=None):
        """Parse CSV text into a list of objects keyed by the header row.

        Options: ``delimiter`` (default ","), ``headers`` (default True). With
        ``headers`` disabled, rows come back as plain lists.
        """
        options = options or {}
        delimiter = options.get("delimiter", ",")
        use_headers = options.get("headers", True)

        source = _Str.mk(text)
        if not source.strip():
            return []

        reader = _csv.reader(_io.StringIO(source), delimiter=delimiter)
        rows = [row for row in reader if row]
        if not rows:
            return []

        if not use_headers:
            return rows

        header, *body = rows
        header = [_Str.mk(column).strip() for column in header]

        results = []
        for row in body:
            entry = Obj()
            for index, column in enumerate(header):
                entry[column] = row[index] if index < len(row) else ""
            results.append(entry)
        return results

    @staticmethod
    def stringify(rows, options=None):
        """Serialise a list of objects (or lists) to CSV text."""
        options = options or {}
        delimiter = options.get("delimiter", ",")
        include_headers = options.get("headers", True)

        if not isinstance(rows, (list, tuple)) or not rows:
            return ""

        buffer = _io.StringIO()
        writer = _csv.writer(buffer, delimiter=delimiter, lineterminator="\n")

        if isinstance(rows[0], dict):
            # Union of keys, preserving first-seen order.
            header = []
            for row in rows:
                for key in row.keys():
                    if key not in header:
                        header.append(key)
            if include_headers:
                writer.writerow(header)
            for row in rows:
                writer.writerow([row.get(key, "") for key in header])
        else:
            for row in rows:
                writer.writerow(row)

        return buffer.getvalue()


def apply(ish):
    """Attach ``io.csv`` to the passed ish instance and return it."""
    ish.io.csv = _Csv
    return ish
