from __future__ import annotations

from typing import Any

Node = dict[str, Any]
Preset = tuple[str, Node]
Move = tuple[str, str, str, float]


def pane(pane_id: str) -> Node:
    return {"type": "pane", "pane_id": pane_id}


def split(direction: str, ratio: float, first: Node, second: Node) -> Node:
    return {
        "type": "split",
        "direction": direction,
        "ratio": ratio,
        "first": first,
        "second": second,
    }


def balanced(ids: list[str], direction: str) -> Node:
    if len(ids) == 1:
        return pane(ids[0])
    midpoint = len(ids) // 2
    return split(
        direction,
        midpoint / len(ids),
        balanced(ids[:midpoint], direction),
        balanced(ids[midpoint:], direction),
    )


def tiled(ids: list[str], direction: str = "right") -> Node:
    if len(ids) == 1:
        return pane(ids[0])
    midpoint = (len(ids) + 1) // 2
    alternate = "down" if direction == "right" else "right"
    return split(
        direction,
        midpoint / len(ids),
        tiled(ids[:midpoint], alternate),
        tiled(ids[midpoint:], alternate),
    )


def same(first: Node, second: Node) -> bool:
    if first["type"] != second["type"]:
        return False
    if first["type"] == "pane":
        return first.get("pane_id") == second.get("pane_id")
    return (
        first["direction"] == second["direction"]
        and abs(float(first["ratio"]) - float(second["ratio"])) < 0.01
        and same(first["first"], second["first"])
        and same(first["second"], second["second"])
    )


def pane_ids(node: Node) -> list[str]:
    if node["type"] == "pane":
        if pane_id := node.get("pane_id"):
            return [pane_id]
        raise ValueError("layout contains a pane without an id")
    return pane_ids(node["first"]) + pane_ids(node["second"])


def first_pane(node: Node) -> str:
    while node["type"] == "split":
        node = node["first"]
    if pane_id := node.get("pane_id"):
        return pane_id
    raise ValueError("layout contains a pane without an id")


def insertion_plan(node: Node) -> list[Move]:
    if node["type"] == "pane":
        return []
    move = (
        first_pane(node["first"]),
        first_pane(node["second"]),
        node["direction"],
        float(node["ratio"]),
    )
    return [move, *insertion_plan(node["first"]), *insertion_plan(node["second"])]


def presets(ids: list[str]) -> list[Preset]:
    candidates = [
        ("even-vertical", balanced(ids, "right")),
        ("even-horizontal", balanced(ids, "down")),
    ]
    if len(ids) > 1:
        candidates += [
            ("main-left", split("right", 0.6, pane(ids[0]), balanced(ids[1:], "down"))),
            ("main-top", split("down", 0.6, pane(ids[0]), balanced(ids[1:], "right"))),
            ("tiled", tiled(ids)),
        ]

    unique: list[Preset] = []
    for name, tree in candidates:
        if not any(same(tree, existing) for _, existing in unique):
            unique.append((name, tree))
    return unique
