"""The `count | sum | avg | min | max` reduction shared by every derived-attribute
evaluator — pulled out on its own so the direct-traversal and batched relationship-derived
evaluators can both use it without either importing the other."""

from __future__ import annotations

from typing import cast


def reduce_values(value: object, reduce: str) -> object:
    values = value if isinstance(value, tuple) else (value,)
    present = tuple(item for item in values if item is not None)
    if reduce == "count":
        return len(present)
    if reduce == "sum":
        return sum(cast(tuple[int | float, ...], present)) if present else 0
    if reduce == "avg":
        return sum(cast(tuple[int | float, ...], present)) / len(present) if present else None
    if reduce == "min":
        return min(cast(tuple[str | int | float, ...], present)) if present else None
    if reduce == "max":
        return max(cast(tuple[str | int | float, ...], present)) if present else None
    raise AssertionError(f"unhandled reduction {reduce!r}")
