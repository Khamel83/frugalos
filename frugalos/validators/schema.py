from __future__ import annotations
import json
from jsonschema import Draft202012Validator

def is_schema_valid(txt: str, schema: dict) -> bool:
    try:
        data = json.loads(txt)
    except Exception:
        return False
    try:
        Draft202012Validator(schema).validate(data)
        return True
    except Exception:
        return False

def try_parse_json(txt: str):
    try:
        return json.loads(txt)
    except Exception:
        return None
