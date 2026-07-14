#!/usr/bin/env python3
"""Resize a Herdr tab without restarting its panes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from layouts import Node, first_pane, insertion_plan, pane_ids, presets, same


class HerdrError(RuntimeError):
    pass


class Herdr:
    def __init__(self) -> None:
        configured = os.environ.get("HERDR_SOCKET_PATH")
        self.socket = (
            Path(configured).expanduser()
            if configured
            else Path.home() / ".config/herdr/herdr.sock"
        )

    @contextmanager
    def layout_lock(self) -> Iterator[None]:
        lock_path = self.socket.with_name(f"{self.socket.name}.layout.lock")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(
            {
                "id": f"pane-layouts-{uuid.uuid4().hex}",
                "method": method,
                "params": params,
            }
        ) + "\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(str(self.socket))
            connection.sendall(payload.encode())
            response = connection.makefile("rb").readline()

        if not response:
            raise HerdrError(f"no response from {method}")
        decoded = json.loads(response)
        if error := decoded.get("error"):
            raise HerdrError(f"{method}: {error.get('message', error.get('code'))}")
        return decoded["result"]

    def layout(self, *, tab_id: str | None = None) -> dict[str, Any]:
        pane_id = None if tab_id else os.environ.get("HERDR_PANE_ID")
        params = {"tab_id": tab_id} if tab_id else ({"pane_id": pane_id} if pane_id else {})
        return self.request("layout.export", params)["layout"]

    def move(
        self,
        pane_id: str,
        destination: dict[str, Any],
        *,
        focus: bool = False,
    ) -> dict[str, Any]:
        result = self.request(
            "pane.move",
            {"pane_id": pane_id, "destination": destination, "focus": focus},
        )["move_result"]
        if not result["changed"]:
            raise HerdrError(f"pane.move: {result.get('reason') or 'move rejected'}")
        return result

    def notify(self, message: str) -> None:
        try:
            self.request(
                "notification.show",
                {"title": "Pane Layouts failed", "body": message, "sound": "none"},
            )
        except Exception:
            pass


def tab_destination(
    tab_id: str,
    target_pane_id: str,
    direction: str,
    ratio: float,
) -> dict[str, Any]:
    return {
        "type": "tab",
        "tab_id": tab_id,
        "target_pane_id": target_pane_id,
        "split": direction,
        "ratio": ratio,
    }


def recover(
    herdr: Herdr,
    staging_tab: str,
    original_tab: str,
    focused_pane: str,
) -> None:
    staged = pane_ids(herdr.layout(tab_id=staging_tab)["root"])
    target = first_pane(herdr.layout(tab_id=original_tab)["root"])
    for pane_id in staged:
        herdr.move(
            pane_id,
            tab_destination(original_tab, target, "right", 0.5),
            focus=pane_id == focused_pane,
        )


def reshape(herdr: Herdr, layout: dict[str, Any], target: Node) -> None:
    ids = pane_ids(layout["root"])
    if len(ids) < 2 or same(layout["root"], target):
        return
    if layout["zoomed"]:
        raise HerdrError("unzoom the tab before changing its layout")

    tab_id = layout["tab_id"]
    focused = layout["focused_pane_id"]
    anchor = first_pane(target)
    staged = [pane_id for pane_id in ids if pane_id != anchor]
    current = {pane_id: pane_id for pane_id in ids}
    staging_tab: str | None = None

    try:
        first = staged[0]
        moved = herdr.move(
            first,
            {
                "type": "new_tab",
                "workspace_id": layout["workspace_id"],
                "label": f"layout-staging-{os.getpid()}",
            },
        )
        staging_tab = moved.get("created_tab", {}).get("tab_id")
        if not staging_tab:
            raise HerdrError("pane.move did not create a staging tab")
        current[first] = moved["pane"]["pane_id"]
        staging_target = current[first]

        for pane_id in staged[1:]:
            moved = herdr.move(
                current[pane_id],
                tab_destination(staging_tab, staging_target, "right", 0.5),
            )
            current[pane_id] = moved["pane"]["pane_id"]

        for target_id, source_id, direction, ratio in insertion_plan(target):
            moved = herdr.move(
                current[source_id],
                tab_destination(tab_id, current[target_id], direction, ratio),
                focus=source_id == focused,
            )
            current[source_id] = moved["pane"]["pane_id"]

        staging_tab = None
    except Exception:
        if staging_tab:
            try:
                recover(herdr, staging_tab, tab_id, current[focused])
            except Exception as error:
                print(
                    f"pane-layouts: recovery failed; panes remain in {staging_tab}: {error}",
                    file=sys.stderr,
                )
        raise


def target_for(action: str, layout: dict[str, Any]) -> Node:
    choices = presets(pane_ids(layout["root"]))
    if action == "equalize":
        return choices[0][1]
    current = next(
        (index for index, (_, tree) in enumerate(choices) if same(layout["root"], tree)),
        -1,
    )
    return choices[(current + 1) % len(choices)][1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("equalize", "cycle"))
    args = parser.parse_args()
    herdr = Herdr()

    try:
        with herdr.layout_lock():
            current = herdr.layout()
            reshape(herdr, current, target_for(args.action, current))
        return 0
    except (HerdrError, OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"pane-layouts: {error}", file=sys.stderr)
        herdr.notify(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
