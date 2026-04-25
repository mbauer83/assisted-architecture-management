from __future__ import annotations


def as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def as_optional_str_list(value: object) -> list[str] | None:
    if value is None or not isinstance(value, list):
        return None
    return [str(item) for item in value]


def as_optional_str_dict(value: object) -> dict[str, str] | None:
    if value is None or not isinstance(value, dict):
        return None
    return {str(key): str(item) for key, item in value.items()}
