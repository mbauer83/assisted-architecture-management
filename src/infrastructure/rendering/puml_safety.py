"""Safety helpers shared by PlantUML renderers and render pipelines."""

from __future__ import annotations

import re
import warnings
from collections.abc import Mapping
from typing import Any

DEFAULT_PUML_SIZE_WARNING_THRESHOLD = 8_000

_LEADING_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)


def strip_leading_puml_frontmatter(puml_body: str) -> str:
    """Remove an optional YAML frontmatter block from the start of a PUML body."""

    return _LEADING_FRONTMATTER_RE.sub("", puml_body, count=1)


def warn_when_puml_exceeds_threshold(
    puml_body: str,
    *,
    threshold: int = DEFAULT_PUML_SIZE_WARNING_THRESHOLD,
) -> None:
    if threshold <= 0 or len(puml_body) <= threshold:
        return
    warnings.warn(
        f"Generated PlantUML body is {len(puml_body)} characters; threshold is {threshold}",
        UserWarning,
        stacklevel=2,
    )


def configured_puml_size_warning_threshold(config: Mapping[str, Any]) -> int:
    rendering = config.get("rendering", {})
    if isinstance(rendering, Mapping) and "output_size_warning_threshold" in rendering:
        return int(rendering["output_size_warning_threshold"])
    if "output_size_warning_threshold" in config:
        return int(config["output_size_warning_threshold"])
    return DEFAULT_PUML_SIZE_WARNING_THRESHOLD
