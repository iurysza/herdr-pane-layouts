#!/usr/bin/env python3
"""Exercise every Pane Layouts action against a disposable live Herdr workspace."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cli import Herdr, HerdrError  # noqa: E402
from layouts import balanced, pane_ids, same  # noqa: E402


class E2EError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


def wait_for_action(
    herdr: Herdr,
    action_id: str,
    context: dict[str, Any],
    timeout: float = 10.0,
) -> dict[str, Any]:
    result = herdr.request(
        "plugin.action.invoke",
        {"action_id": f"layouts.{action_id}", "context": context},
    )
    log_id = result["log"]["log_id"]
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        logs = herdr.request(
            "plugin.log.list", {"plugin_id": "layouts", "limit": 20}
        )["logs"]
        log = next((entry for entry in logs if entry["log_id"] == log_id), None)
        if log and log["status"] == "succeeded":
            print(f"ok: {action_id}")
            return log
        if log and log["status"] == "failed":
            detail = log.get("stderr") or log.get("error") or "unknown error"
            raise E2EError(f"{action_id} failed: {detail.strip()}")
        time.sleep(0.05)

    raise E2EError(f"{action_id} timed out")


def export_layout(herdr: Herdr, tab_id: str) -> dict[str, Any]:
    return herdr.request("layout.export", {"tab_id": tab_id})["layout"]


def ratios(node: dict[str, Any]) -> list[tuple[str, float]]:
    if node["type"] == "pane":
        return []
    return [
        (node["direction"], round(float(node["ratio"]), 4)),
        *ratios(node["first"]),
        *ratios(node["second"]),
    ]


def shell_pids(herdr: Herdr, tab_id: str) -> set[int]:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        ids = pane_ids(export_layout(herdr, tab_id)["root"])
        pids = {
            herdr.request("pane.process_info", {"pane_id": pane_id})[
                "process_info"
            ].get("shell_pid")
            for pane_id in ids
        }
        if None not in pids and len(pids) == len(ids):
            return pids
        time.sleep(0.05)
    raise E2EError("test pane shell processes did not become ready")


def main() -> int:
    require(os.environ.get("HERDR_ENV") == "1", "run this test inside Herdr")
    herdr = Herdr()
    workspace_id: str | None = None

    try:
        plugins = herdr.request("plugin.list", {})["plugins"]
        plugin = next(
            (entry for entry in plugins if entry["plugin_id"] == "layouts"), None
        )
        require(plugin is not None, "layouts plugin is not linked")
        require(plugin["enabled"], "layouts plugin is disabled")

        actions = herdr.request(
            "plugin.action.list", {"plugin_id": "layouts"}
        )["actions"]
        require(len(actions) == 6, f"expected 6 actions, found {len(actions)}")

        created = herdr.request(
            "workspace.create",
            {
                "cwd": str(ROOT),
                "label": f"pane-layouts-e2e-{os.getpid()}",
                "focus": False,
            },
        )
        workspace_id = created["workspace"]["workspace_id"]
        tab_id = created["tab"]["tab_id"]
        first_id = created["root_pane"]["pane_id"]

        second = herdr.request(
            "pane.split",
            {
                "target_pane_id": first_id,
                "direction": "right",
                "ratio": 0.7,
                "focus": False,
            },
        )["pane"]["pane_id"]
        herdr.request(
            "pane.split",
            {
                "target_pane_id": second,
                "direction": "down",
                "ratio": 0.6,
                "focus": False,
            },
        )

        original = export_layout(herdr, tab_id)
        original_ids = pane_ids(original["root"])
        original_pids = shell_pids(herdr, tab_id)
        context = {
            "workspace_id": workspace_id,
            "workspace_cwd": str(ROOT),
            "tab_id": tab_id,
            "focused_pane_id": first_id,
            "focused_pane_cwd": str(ROOT),
            "invocation_source": "e2e",
        }

        wait_for_action(herdr, "equalize", context)
        equalized = export_layout(herdr, tab_id)
        require(
            same(equalized["root"], balanced(original_ids, "right")),
            "equalize did not produce even vertical columns",
        )

        before = ratios(equalized["root"])
        wait_for_action(herdr, "resize-right", context)
        after = export_layout(herdr, tab_id)
        require(ratios(after["root"]) != before, "resize-right changed no ratio")

        rightmost = pane_ids(after["root"])[-1]
        context["focused_pane_id"] = rightmost
        before = ratios(after["root"])
        wait_for_action(herdr, "resize-left", context)
        after = export_layout(herdr, tab_id)
        require(ratios(after["root"]) != before, "resize-left changed no ratio")

        context["focused_pane_id"] = first_id
        wait_for_action(herdr, "equalize", context)
        wait_for_action(herdr, "cycle", context)
        horizontal = export_layout(herdr, tab_id)
        require(
            same(horizontal["root"], balanced(original_ids, "down")),
            "cycle did not advance to even horizontal rows",
        )

        before = ratios(horizontal["root"])
        wait_for_action(herdr, "resize-down", context)
        after = export_layout(herdr, tab_id)
        require(ratios(after["root"]) != before, "resize-down changed no ratio")

        bottom = pane_ids(after["root"])[-1]
        context["focused_pane_id"] = bottom
        before = ratios(after["root"])
        wait_for_action(herdr, "resize-up", context)
        after = export_layout(herdr, tab_id)
        require(ratios(after["root"]) != before, "resize-up changed no ratio")

        require(
            shell_pids(herdr, tab_id) == original_pids,
            "layout actions replaced a running pane process",
        )
        print("ok: all pane processes preserved")
        return 0
    except (E2EError, HerdrError, KeyError, OSError, ValueError) as error:
        print(f"e2e failed: {error}", file=sys.stderr)
        return 1
    finally:
        if workspace_id:
            try:
                herdr.request("workspace.close", {"workspace_id": workspace_id})
            except Exception as error:
                print(f"cleanup failed for {workspace_id}: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
