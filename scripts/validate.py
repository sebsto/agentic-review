"""Minimal JSON Schema check for the schemas in schemas/. Standard library only.

Supports: type (object, string, integer, boolean), required, properties,
additionalProperties=false, enum, minimum, maxLength. That is all the schemas use.
"""

import json

from common import ROOT

TYPES = {"object": dict, "string": str, "integer": int, "boolean": bool}


def check(value, schema: dict, path: str = "$") -> list[str]:
    """Return a list of problems; an empty list means the value is valid."""
    problems: list[str] = []
    kind = schema.get("type")
    if kind:
        expected = TYPES[kind]
        if not isinstance(value, expected) or (kind == "integer" and isinstance(value, bool)):
            return [f"{path}: expected {kind}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: {value!r} not in {schema['enum']}")
    if "minimum" in schema and value < schema["minimum"]:
        problems.append(f"{path}: below minimum")
    if "maxLength" in schema and len(value) > schema["maxLength"]:
        problems.append(f"{path}: too long")
    if kind == "object":
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{path}: missing {key}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                problems += check(item, properties[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{path}: unexpected {key}")
    return problems


def load_schema(name: str) -> dict:
    """Load schemas/<name>.schema.json."""
    return json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text())
