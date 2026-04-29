from __future__ import annotations

from collections import defaultdict
from typing import TypeVar

T = TypeVar("T")


def select_deepest_common_parent(
    endpoint_aliases: set[str],
    direct_parent_by_alias: dict[str, str],
) -> str | None:
    if not endpoint_aliases:
        return None

    chains_by_alias: dict[str, list[str]] = {}
    for alias in endpoint_aliases:
        chain: list[str] = []
        current = alias
        while parent := direct_parent_by_alias.get(current):
            chain.append(parent)
            current = parent
        if not chain:
            return None
        chains_by_alias[alias] = chain

    common = set(chains_by_alias[next(iter(chains_by_alias))])
    for chain in chains_by_alias.values():
        common &= set(chain)
    if not common:
        return None

    def _distance(alias: str, parent_alias: str) -> int:
        return chains_by_alias[alias].index(parent_alias)

    return min(
        common,
        key=lambda parent_alias: (
            max(_distance(alias, parent_alias) for alias in chains_by_alias),
            sum(_distance(alias, parent_alias) for alias in chains_by_alias),
            parent_alias,
        ),
    )


def build_visual_nesting(
    *,
    item_by_alias: dict[str, T],
    structural_edges: list[tuple[str, str]],
    neighbor_edges: list[tuple[str, str]],
    junction_aliases: set[str],
) -> tuple[dict[str, list[T]], set[str]]:
    children_map: dict[str, list[T]] = defaultdict(list)
    direct_parent_by_alias: dict[str, str] = {}
    nested_aliases: set[str] = set()
    junction_neighbors: dict[str, set[str]] = defaultdict(set)

    for source_alias, target_alias in structural_edges:
        if target_alias in item_by_alias:
            children_map[source_alias].append(item_by_alias[target_alias])
            direct_parent_by_alias[target_alias] = source_alias
            nested_aliases.add(target_alias)

    for source_alias, target_alias in neighbor_edges:
        if source_alias in junction_aliases:
            junction_neighbors[source_alias].add(target_alias)
        if target_alias in junction_aliases:
            junction_neighbors[target_alias].add(source_alias)

    visited: set[str] = set()
    for junction_alias in sorted(junction_aliases):
        if junction_alias in visited or junction_alias in direct_parent_by_alias:
            continue
        component: list[str] = []
        endpoint_aliases: set[str] = set()
        stack = [junction_alias]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor_alias in junction_neighbors.get(current, ()):
                if neighbor_alias in junction_aliases:
                    if neighbor_alias not in visited:
                        stack.append(neighbor_alias)
                    continue
                endpoint_aliases.add(neighbor_alias)

        parent_alias = select_deepest_common_parent(endpoint_aliases, direct_parent_by_alias)
        if parent_alias is None:
            continue
        for component_alias in component:
            if component_alias in nested_aliases or component_alias not in item_by_alias:
                continue
            children_map[parent_alias].append(item_by_alias[component_alias])
            nested_aliases.add(component_alias)

    return children_map, nested_aliases


def build_nested_layout_lines(
    *,
    child_aliases: list[str],
    flow_edges: list[tuple[str, str]],
    junction_aliases: set[str],
    main_axis: str,
    branch_axis: str,
    indent: str,
) -> list[str]:
    if len(child_aliases) < 2:
        return []

    child_alias_set = set(child_aliases)
    original_index = {alias: index for index, alias in enumerate(child_aliases)}

    def _original_position(alias: str) -> int:
        return original_index.get(alias, len(original_index))

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {alias: 0 for alias in child_aliases}

    for src_alias, tgt_alias in flow_edges:
        if src_alias not in child_alias_set or tgt_alias not in child_alias_set or tgt_alias in outgoing[src_alias]:
            continue
        outgoing[src_alias].add(tgt_alias)
        incoming[tgt_alias].add(src_alias)
        indegree[tgt_alias] += 1

    queue = sorted([alias for alias in child_aliases if indegree[alias] == 0], key=_original_position)
    ordered_aliases: list[str] = []
    while queue:
        current = queue.pop(0)
        ordered_aliases.append(current)
        for neighbor in sorted(outgoing.get(current, ()), key=_original_position):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort(key=_original_position)

    for alias in child_aliases:
        if alias not in ordered_aliases:
            ordered_aliases.append(alias)

    order_index = {alias: index for index, alias in enumerate(ordered_aliases)}

    def _ordered_position(alias: str) -> int:
        return order_index.get(alias, len(order_index))

    pair_axis_overrides: dict[tuple[str, str], str] = {}
    extra_lines: list[str] = []
    for junction_alias in ordered_aliases:
        if junction_alias not in junction_aliases:
            continue
        successors = sorted(
            [alias for alias in outgoing.get(junction_alias, ()) if alias in child_alias_set],
            key=_ordered_position,
        )
        if len(successors) >= 2:
            for successor in successors:
                extra_lines.append(f"{indent}{junction_alias} -[hidden]{main_axis}- {successor}")
            for index in range(len(successors) - 1):
                pair_axis_overrides[(successors[index], successors[index + 1])] = branch_axis
        predecessors = sorted(
            [alias for alias in incoming.get(junction_alias, ()) if alias in child_alias_set],
            key=_ordered_position,
        )
        if len(predecessors) >= 2:
            for predecessor in predecessors:
                extra_lines.append(f"{indent}{predecessor} -[hidden]{main_axis}- {junction_alias}")
            for index in range(len(predecessors) - 1):
                pair_axis_overrides[(predecessors[index], predecessors[index + 1])] = branch_axis

    lines: list[str] = []
    for index in range(len(ordered_aliases) - 1):
        left = ordered_aliases[index]
        right = ordered_aliases[index + 1]
        axis = pair_axis_overrides.get((left, right), main_axis)
        lines.append(f"{indent}{left} -[hidden]{axis}- {right}")
    return [*lines, *extra_lines]


def build_branch_direction_hints(
    *,
    child_aliases: list[str],
    flow_edges: list[tuple[str, str]],
    junction_aliases: set[str],
    branch_axis: str,
) -> dict[tuple[str, str], str]:
    if len(child_aliases) < 2:
        return {}

    child_alias_set = set(child_aliases)
    original_index = {alias: index for index, alias in enumerate(child_aliases)}

    def _original_position(alias: str) -> int:
        return original_index.get(alias, len(original_index))

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for src_alias, tgt_alias in flow_edges:
        if src_alias not in child_alias_set or tgt_alias not in child_alias_set:
            continue
        outgoing[src_alias].add(tgt_alias)
        incoming[tgt_alias].add(src_alias)

    hints: dict[tuple[str, str], str] = {}
    for junction_alias in child_aliases:
        if junction_alias not in junction_aliases:
            continue
        for group in (
            sorted([alias for alias in outgoing.get(junction_alias, ()) if alias in child_alias_set], key=_original_position),
            sorted([alias for alias in incoming.get(junction_alias, ()) if alias in child_alias_set], key=_original_position),
        ):
            if len(group) < 2:
                continue
            for left_index, left_alias in enumerate(group):
                for right_alias in group[left_index + 1 :]:
                    if branch_axis == "right":
                        hints[(left_alias, right_alias)] = "right"
                        hints[(right_alias, left_alias)] = "left"
                    else:
                        hints[(left_alias, right_alias)] = "down"
                        hints[(right_alias, left_alias)] = "up"
    return hints
