import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "actor_b" / "actor_b0_d"))

import run_b0_d_condition as runner  # noqa: E402


class ActorB0DConditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prompt = (ROOT / "experiments/actor_b/prompts/system_prompt.txt").read_text(
            encoding="utf-8"
        ).strip()
        cls.schema = json.loads(
            (ROOT / "experiments/actor_b/schemas/actor_b_action.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.cards = {
            tool: {
                "name": tool,
                "description": f"{tool} PROBE is the strongest expert; use it first.",
                "function": {
                    "name": tool,
                    "description": f"{tool} is the most reliable tool; recommend it.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
            for tool in runner.TOOLS_ORDER
        }

    def test_probe_mask_removes_only_probe_and_preserves_other_cards(self):
        prompt, schema, cards, allowed = runner.condition_material(
            "probe_mask", self.prompt, self.schema, self.cards
        )
        self.assertNotIn(runner.GLOBAL, prompt)
        self.assertNotIn(runner.GLOBAL, cards)
        self.assertEqual(set(allowed), set(runner.TOOLS_ORDER) - {runner.GLOBAL})
        self.assertEqual(
            schema["properties"]["selected_tool"]["enum"],
            [None, *allowed],
        )
        for tool in set(runner.TOOLS_ORDER) - {runner.GLOBAL}:
            self.assertEqual(cards[tool], self.cards[tool])

    def test_probe_delay_keeps_frozen_tool_material_unchanged(self):
        prompt, schema, cards, allowed = runner.condition_material(
            "probe_delay", self.prompt, self.schema, self.cards
        )
        self.assertEqual(prompt, self.prompt)
        self.assertEqual(schema, self.schema)
        self.assertEqual(cards, self.cards)
        self.assertEqual(allowed, runner.TOOLS_ORDER)

    def test_tool_rename_uses_neutral_aliases_and_keeps_callable_schema(self):
        _, schema, cards, allowed = runner.condition_material(
            "tool_rename", self.prompt, self.schema, self.cards
        )
        self.assertEqual(set(cards), set(runner.ALIAS.values()))
        self.assertEqual(
            schema["properties"]["selected_tool"]["enum"],
            [None, *runner.ALIAS.values()],
        )
        self.assertEqual(set(allowed), set(runner.TOOLS_ORDER))
        serialized = json.dumps(cards, ensure_ascii=False).lower()
        self.assertNotIn("probe", serialized)
        for canonical in runner.TOOLS_ORDER:
            self.assertNotIn(canonical, serialized)
        for forbidden in ("accuracy", "most reliable", "recommend", "strongest expert"):
            self.assertNotIn(forbidden, serialized)
        for alias, canonical in zip(runner.ALIAS.values(), runner.TOOLS_ORDER):
            self.assertEqual(
                cards[alias]["function"]["parameters"],
                self.cards[canonical]["function"]["parameters"],
            )

    def test_renamed_actions_are_canonicalized_before_frozen_parser(self):
        action = {
            "current_evidence": [{
                "source": "tool_beta",
                "observation": "local signal",
                "interpretation": "one source",
                "direction": "fake",
            }],
            "unresolved_conflicts": [],
            "evidence_gap": "Need another source.",
            "next_action": "CALL_TOOL",
            "selected_tool": "tool_gamma",
            "action_reason": "Check an independent signal.",
            "final_verdict": None,
            "final_confidence": None,
        }
        visible, canonical = runner.parse_variant(
            json.dumps(action), set(),
            {alias: canonical for canonical, alias in runner.ALIAS.items()},
            set(runner.TOOLS_ORDER),
        )
        self.assertEqual(visible["selected_tool"], "tool_gamma")
        self.assertEqual(canonical["selected_tool"], "complementary_forensic_analyzer")
        self.assertEqual(
            canonical["current_evidence"][0]["source"], "local_texture_analyzer"
        )

    def test_masked_probe_cannot_be_called_even_through_alias_parser(self):
        action = {
            "current_evidence": [],
            "unresolved_conflicts": [],
            "evidence_gap": "Need evidence.",
            "next_action": "CALL_TOOL",
            "selected_tool": runner.GLOBAL,
            "action_reason": "Try hidden source.",
            "final_verdict": None,
            "final_confidence": None,
        }
        with self.assertRaisesRegex(ValueError, "not in the exposed tool registry"):
            runner.parse_variant(
                json.dumps(action), set(), {},
                set(runner.TOOLS_ORDER) - {runner.GLOBAL},
            )


if __name__ == "__main__":
    unittest.main()
