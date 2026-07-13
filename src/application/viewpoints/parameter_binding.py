"""Bind declared viewpoint parameters to one execution request."""

from __future__ import annotations

from collections.abc import Mapping

from src.application.viewpoints.ports import RepositoryReadAccess
from src.domain.viewpoint_bindings import QueryParameter
from src.domain.viewpoints import ExecutableViewpointQuery


class ViewpointParameterError(ValueError):
    """Raised when supplied query parameters do not match the declaration."""

    def __init__(self, code: str, parameter: str) -> None:
        super().__init__(f"{code}: {parameter}")
        self.code = code
        self.parameter = parameter


def bind_parameters(
    query: ExecutableViewpointQuery, supplied: Mapping[str, object] | None, read_access: RepositoryReadAccess
) -> dict[str, object]:
    values = dict(supplied or {})
    declared = {parameter.name: parameter for parameter in query.parameters}
    for name in values:
        if name not in declared:
            raise ViewpointParameterError("unknown-parameter", name)
    resolved: dict[str, object] = {}
    for name, parameter in declared.items():
        if name not in values:
            if parameter.default is not None:
                resolved[name] = parameter.default
            elif parameter.required:
                raise ViewpointParameterError("missing-parameter", name)
            continue
        value = values[name]
        if not _matches_parameter(value, parameter):
            raise ViewpointParameterError("parameter-type-mismatch", name)
        if parameter.value_type != "entity-id" or (
            isinstance(value, str) and read_access.get_entity(value) is not None
        ):
            resolved[name] = value
    return resolved


def _matches_parameter(value: object, parameter: QueryParameter) -> bool:
    if parameter.value_type in {"string", "slug", "date", "entity-id"}:
        return isinstance(value, str)
    if parameter.value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if parameter.value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, bool) if parameter.value_type == "boolean" else False
