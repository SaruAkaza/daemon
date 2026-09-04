from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = (ROOT / "schemas").resolve()


class ContractValidationError(ValueError):
    """Raised when contract schema loading or payload validation fails."""
    pass


def load_json(path: Path | str) -> dict[str, Any]:
    """Load and parse a JSON file, ensuring top-level object structure.

    Raises:
        ContractValidationError: If the file does not exist, has invalid JSON syntax,
                                 or the top-level element is not an object.
    """
    p = Path(path)
    if not p.is_file():
        raise ContractValidationError(f"JSON file not found: {p}")

    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Invalid JSON syntax in {p}: {e}") from e
    except Exception as e:
        raise ContractValidationError(f"Failed to read JSON file {p}: {e}") from e

    if not isinstance(data, dict):
        raise ContractValidationError(
            f"Top-level JSON payload in {p} must be an object (dict), got {type(data).__name__}"
        )

    return data


def _schema_path(name: str) -> Path:
    """Resolve schema name to a safe Path within the schemas directory.

    Raises:
        ContractValidationError: If path traversal is attempted or schema does not exist.
    """
    if not isinstance(name, str) or not name.strip():
        raise ContractValidationError("Schema name must be a non-empty string.")

    if ".." in name or "/" in name or "\\" in name:
        raise ContractValidationError(f"Invalid schema name or path traversal attempt: {name}")

    filename = name if name.endswith(".json") else f"{name}.schema.json"
    target = (SCHEMAS_DIR / filename).resolve()

    try:
        target.relative_to(SCHEMAS_DIR.resolve())
    except ValueError:
        raise ContractValidationError(f"Path traversal detected for schema name: {name}")

    if not target.is_file():
        raise ContractValidationError(f"Schema file not found: {name} (searched at {target})")

    return target


def load_schema(name: str) -> dict[str, Any]:
    """Load and validate a JSON schema by name against Draft 2020-12.

    Raises:
        ContractValidationError: If the schema cannot be loaded or is not a valid
                                 Draft 2020-12 schema.
    """
    path = _schema_path(name)
    schema = load_json(path)

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        raise ContractValidationError(f"Invalid JSON Schema structure in '{name}': {e.message}") from e
    except Exception as e:
        raise ContractValidationError(f"Failed validating schema '{name}': {e}") from e

    return schema


def validate_payload(schema_name: str, payload: dict[str, Any]) -> None:
    """Validate a dictionary payload against the specified schema.

    Raises:
        ContractValidationError: If the payload fails validation or schema is invalid.
    """
    if not isinstance(payload, dict):
        raise ContractValidationError(
            f"Payload to validate against '{schema_name}' must be a dict, got {type(payload).__name__}"
        )

    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)

    errors = sorted(validator.iter_errors(payload), key=lambda e: [str(p) for p in e.path])
    if errors:
        err = errors[0]
        field_path = ".".join(str(p) for p in err.path) if err.path else "<root>"
        raise ContractValidationError(
            f"Validation failed against schema '{schema_name}' at '{field_path}': {err.message}"
        )
