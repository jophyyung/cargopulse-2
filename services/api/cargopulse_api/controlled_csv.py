"""Bounded controlled intake and spreadsheet-oriented report serialization.

The canonical models remain authoritative. Errors here contain code-owned messages,
never uploaded values. Report CSV escapes presentation hazards; JSON remains the
lossless evidence format. CSV escaping is not a malware scan or a guarantee about
spreadsheets that are subsequently edited, saved and reopened.
"""

import csv
import io
import json
from decimal import DecimalException

from cargopulse_contracts import CargoUnit, ScenarioSnapshot
from pydantic import ValidationError

FORMULA_PREFIXES = ("=", "+", "-", "@", "＝", "＋", "－", "＠")
JSON_COLUMNS = frozenset({"pieces", "serviceability", "security"})
BOOLEAN_COLUMNS = frozenset({"requires_cold_chain", "atomic_whole_uld"})
MAX_ROWS = 1200


class ControlledCSVError(ValueError):
    """A public validation message containing no untrusted input."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ControlledCSVError("Duplicate JSON keys are not allowed")
        result[key] = value
    return result


def _reject_constant(value):
    raise ControlledCSVError("JSON must contain finite values")


def _json(value, location):
    try:
        return json.loads(value, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except ControlledCSVError:
        raise
    except (ValueError, RecursionError):
        raise ControlledCSVError(f"Invalid or excessively nested JSON in {location}") from None


def _has_control(value):
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _json_cell(value, line):
    decoded = _json(value, f"row {line}")
    pending = [decoded]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and _has_control(item):
            raise ControlledCSVError(f"row {line}: control characters are not allowed")
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return decoded


def parse_controlled_csv(raw: bytes, metadata: str) -> ScenarioSnapshot:
    """Reject ambiguity before mapping cells; stop at the first excess ULD row."""
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        fields = next(reader, [])
        if not fields or len(set(fields)) != len(fields):
            raise ControlledCSVError("CSV requires unique, nonempty column names")
        known = CargoUnit.model_fields
        if any(field not in known for field in fields):
            raise ControlledCSVError("CSV contains an empty or unsupported column name")
        required = {field for field, info in known.items() if info.is_required()}
        units = []
        for row in reader:
            if not row:
                continue
            if len(units) >= MAX_ROWS:
                raise ControlledCSVError("CSV requires 1-1200 ULD rows")
            line = reader.line_num
            if len(row) != len(fields):
                raise ControlledCSVError(f"row {line}: column mismatch")
            unit = {}
            for key, value in zip(fields, row, strict=True):
                if _has_control(value):
                    raise ControlledCSVError(f"row {line}: control characters are not allowed")
                if value.lstrip().startswith(FORMULA_PREFIXES):
                    raise ControlledCSVError(f"row {line}: unsafe formula prefix")
                if key in JSON_COLUMNS:
                    unit[key] = _json_cell(value, line)
                elif key in BOOLEAN_COLUMNS:
                    if value not in ("true", "false"):
                        raise ControlledCSVError(f"row {line}: explicit boolean required")
                    unit[key] = value == "true"
                elif value != "":
                    unit[key] = value
            units.append(unit)
        if not units:
            raise ControlledCSVError("CSV requires 1-1200 ULD rows")
        if not required.issubset(fields):
            raise ControlledCSVError("CSV is missing required ULD columns")
        data = _json(metadata, "metadata")
        if not isinstance(data, dict) or "cargo_units" in data:
            raise ControlledCSVError("Metadata must be a snapshot object without cargo_units")
        data["cargo_units"] = units
        return ScenarioSnapshot.model_validate(data)
    except ControlledCSVError:
        raise
    except UnicodeError:
        raise ControlledCSVError("CSV must use valid UTF-8") from None
    except csv.Error:
        raise ControlledCSVError(
            "CSV has malformed quoting or exceeds the parser field limit"
        ) from None
    except (ValidationError, ValueError, TypeError, DecimalException, RecursionError):
        # Pydantic exceptions can include private input. Arithmetic errors from
        # domain-model validation must also stay inside this public boundary.
        raise ControlledCSVError("CSV or metadata does not match the snapshot schema") from None


class SpreadsheetCSVWriter:
    """Quote every report cell and neutralize formula/control prefixes once."""

    def __init__(self, stream):
        self.writer = csv.writer(stream, quoting=csv.QUOTE_ALL)

    def writerow(self, values):
        cells = []
        for value in values:
            text = "" if value is None else str(value)
            text = "".join(
                f"\\x{ord(character):02x}"
                if ord(character) < 32 or ord(character) == 127
                else character
                for character in text
            )
            if text.lstrip().startswith(FORMULA_PREFIXES):
                text = "'" + text
            cells.append(text)
        self.writer.writerow(cells)
