from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import layouts


class LayoutTreesTest(unittest.TestCase):
    def test_balanced_vertical_contains_every_pane(self) -> None:
        tree = layouts.balanced(["p1", "p2", "p3"], "right")

        self.assertEqual(layouts.pane_ids(tree), ["p1", "p2", "p3"])
        self.assertEqual(tree["direction"], "right")
        self.assertAlmostEqual(tree["ratio"], 1 / 3)

    def test_presets_are_unique(self) -> None:
        presets = layouts.presets(["p1", "p2", "p3"])

        self.assertEqual(
            [name for name, _ in presets],
            ["even-vertical", "even-horizontal", "main-left", "main-top", "tiled"],
        )
        for index, (_, tree) in enumerate(presets):
            self.assertFalse(
                any(layouts.same(tree, other) for _, other in presets[:index])
            )

    def test_insertion_plan_builds_parents_before_children(self) -> None:
        target = layouts.split(
            "right",
            0.6,
            layouts.pane("p1"),
            layouts.split(
                "down", 0.5, layouts.pane("p2"), layouts.pane("p3")
            ),
        )

        self.assertEqual(
            layouts.insertion_plan(target),
            [("p1", "p2", "right", 0.6), ("p2", "p3", "down", 0.5)],
        )

    def test_single_pane_has_one_preset(self) -> None:
        presets = layouts.presets(["p1"])

        self.assertEqual(len(presets), 1)
        self.assertTrue(layouts.same(presets[0][1], layouts.pane("p1")))


if __name__ == "__main__":
    unittest.main()
