"""CPU-only structural checks for the paired P0 smoke-test ledger.

Passing these checks does not establish that model state was restored correctly.
That requires the uninterrupted-versus-resumed A0 test on the Actor host.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .schema import Outcome


ARMS = frozenset({"A0", "A1", "A2"})
MANIFEST_FIELDS = ("sample_id", "source_group_id", "label", "image_sha256", "split")
PREFIX_FIELDS = (
    "episode_id", "sample_id", "source_group_id", "checkpoint_id",
    "reached", "prefix_hash", "image_sha256", "messages_sha256",
    "tool_outputs_sha256", "actor_hash", "prompt_hash", "tool_hash",
    "channel_hash", "decoding_seed",
)
BRANCH_PREFIX_FIELDS = (
    "image_sha256", "messages_sha256", "tool_outputs_sha256",
    "actor_hash", "prompt_hash", "tool_hash", "channel_hash", "decoding_seed",
)
FORBIDDEN_PREFIX_KEYS = frozenset({
    "ground_truth", "correct", "outcomes", "predicted_gain", "manifest",
})


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{number}: expected a JSON object")
            rows.append(row)
    return rows


def _forbidden_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = FORBIDDEN_PREFIX_KEYS.intersection(value)
        for nested in value.values():
            found |= _forbidden_keys(nested)
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for nested in value:
            found |= _forbidden_keys(nested)
        return found
    return set()


def validate_p0(
    manifest: list[dict[str, Any]],
    prefixes: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed on incomplete or inconsistent P0 files."""
    if not manifest:
        raise ValueError("manifest is empty")
    if not prefixes:
        raise ValueError("prefix ledger is empty")
    synthetic_values = [row.get("synthetic", False) for row in manifest]
    if any(type(value) is not bool for value in synthetic_values):
        raise ValueError("manifest synthetic flags must be JSON booleans")
    synthetic_flags = set(synthetic_values)
    if synthetic_flags not in ({False}, {True}):
        raise ValueError("manifest mixes synthetic and observed rows")
    synthetic = True in synthetic_flags
    if synthetic and any(row.get("synthetic") is not True for row in prefixes + outcomes):
        raise ValueError("synthetic manifest requires synthetic prefix and outcome rows")
    samples: dict[str, dict[str, Any]] = {}
    image_hashes: dict[str, tuple[str, str]] = {}
    group_splits: dict[str, str] = {}
    for row in manifest:
        missing = [field for field in MANIFEST_FIELDS if field not in row]
        if missing:
            raise ValueError(f"manifest missing fields: {missing}")
        sample_id = row["sample_id"]
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError("manifest sample_id must be a non-empty string")
        if sample_id in samples:
            raise ValueError(f"duplicate manifest sample_id {sample_id}")
        for field in ("source_group_id", "image_sha256", "split"):
            if not isinstance(row[field], str) or not row[field]:
                raise ValueError(f"{sample_id}: manifest {field} must be a non-empty string")
        if row["label"] not in ("real", "fake"):
            raise ValueError(f"{sample_id}: manifest label must be real or fake")
        group = row["source_group_id"]
        split = row["split"]
        if group in group_splits and group_splits[group] != split:
            raise ValueError(f"{group}: source group crosses splits")
        group_splits[group] = split
        image_hash = row["image_sha256"]
        image_identity = (group, row["label"])
        if image_hash in image_hashes and image_hashes[image_hash] != image_identity:
            raise ValueError(f"{sample_id}: image hash crosses source group or label")
        image_hashes[image_hash] = image_identity
        samples[sample_id] = row

    by_episode: dict[str, dict[str, Any]] = {}
    sample_seed_pairs: set[tuple[str, int]] = set()
    for row in prefixes:
        missing = [field for field in PREFIX_FIELDS if field not in row]
        if missing:
            raise ValueError(f"prefix missing fields: {missing}")
        episode_id = row["episode_id"]
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError("episode_id must be a non-empty string")
        if episode_id in by_episode:
            raise ValueError(f"duplicate prefix for {episode_id}")
        if type(row["reached"]) is not bool:
            raise ValueError(f"{episode_id}: reached must be a JSON boolean")
        if not row["reached"] and (not isinstance(row.get("reason"), str) or not row["reason"]):
            raise ValueError(f"{episode_id}: unreached checkpoint needs a reason")
        for field in PREFIX_FIELDS:
            if field in ("reached", "decoding_seed"):
                continue
            if not isinstance(row[field], str) or not row[field]:
                raise ValueError(f"{episode_id}: {field} must be a non-empty string")
        if isinstance(row["decoding_seed"], bool) or not isinstance(row["decoding_seed"], int):
            raise ValueError(f"{episode_id}: decoding_seed must be an integer")
        sample_seed = (row["sample_id"], row["decoding_seed"])
        if sample_seed in sample_seed_pairs:
            raise ValueError(f"{episode_id}: duplicate sample and prefix seed")
        sample_seed_pairs.add(sample_seed)
        sample = samples.get(row["sample_id"])
        if sample is None:
            raise ValueError(f"{episode_id}: sample_id missing from manifest")
        if row["source_group_id"] != sample["source_group_id"]:
            raise ValueError(f"{episode_id}: source group mismatch with manifest")
        if row["image_sha256"] != sample["image_sha256"]:
            raise ValueError(f"{episode_id}: image hash mismatch with manifest")
        forbidden = set(_forbidden_keys(row))
        if "label" in row:
            forbidden.add("label")
        if forbidden:
            raise ValueError(f"{episode_id}: future or label keys in prefix: {sorted(forbidden)}")
        by_episode[episode_id] = row

    missing_samples = sorted(samples.keys() - {row["sample_id"] for row in prefixes})
    if missing_samples:
        raise ValueError(f"manifest samples missing from initial episodes: {missing_samples[:5]}")

    seen: dict[str, set[str]] = {episode_id: set() for episode_id in by_episode}
    arm_versions: dict[str, str] = {}
    for raw in outcomes:
        outcome = Outcome.from_dict(raw)
        episode_id = outcome.episode_id
        if episode_id not in by_episode:
            raise ValueError(f"outcome has unknown episode {episode_id}")
        prefix = by_episode[episode_id]
        if not prefix["reached"]:
            raise ValueError(f"unreached episode {episode_id} has an outcome")
        if outcome.arm not in ARMS:
            raise ValueError(f"{episode_id}: unknown arm {outcome.arm}")
        if outcome.arm in seen[episode_id]:
            raise ValueError(f"{episode_id}: duplicate arm {outcome.arm}")
        if raw.get("prefix_hash") != prefix["prefix_hash"]:
            raise ValueError(f"{episode_id}/{outcome.arm}: prefix hash mismatch")
        for field in BRANCH_PREFIX_FIELDS:
            if raw.get(field) != prefix[field]:
                raise ValueError(f"{episode_id}/{outcome.arm}: pre-branch {field} mismatch")
        if not isinstance(raw.get("arm_version"), str) or not raw["arm_version"]:
            raise ValueError(f"{episode_id}/{outcome.arm}: arm_version is required")
        previous_version = arm_versions.setdefault(outcome.arm, raw["arm_version"])
        if raw["arm_version"] != previous_version:
            raise ValueError(f"{episode_id}/{outcome.arm}: arm_version changed within run")
        answer = raw.get("answer")
        if answer not in ("real", "fake", "abstain"):
            raise ValueError(f"{episode_id}/{outcome.arm}: invalid answer")
        if outcome.abstained != (answer == "abstain") or (outcome.abstained and outcome.correct):
            raise ValueError(f"{episode_id}/{outcome.arm}: answer/abstention conflict")
        label = samples[prefix["sample_id"]]["label"]
        if outcome.correct != (answer == label):
            raise ValueError(f"{episode_id}/{outcome.arm}: correct disagrees with manifest label")
        seen[episode_id].add(outcome.arm)

    for episode_id, prefix in by_episode.items():
        expected = ARMS if prefix["reached"] else frozenset()
        if seen[episode_id] != expected:
            missing = sorted(expected - seen[episode_id])
            raise ValueError(f"{episode_id}: incomplete arm set; missing {missing}")

    groups = Counter(row["source_group_id"] for row in prefixes)
    return {
        "status": "structurally_valid",
        "data_kind": "synthetic_file_contract_check" if synthetic else "observed_unverified",
        "n_manifest_samples": len(manifest),
        "n_initial_episodes": len(prefixes),
        "n_reached": sum(row["reached"] for row in prefixes),
        "n_unreached": sum(not row["reached"] for row in prefixes),
        "n_outcomes": len(outcomes),
        "n_source_groups": len(groups),
        "manifest_label_counts": dict(sorted(Counter(row["label"] for row in manifest).items())),
        "unreached_reasons": dict(sorted(Counter(
            row["reason"] for row in prefixes if not row["reached"]
        ).items())),
        "checks_not_performed": [
            "actual model/image/tool state equivalence across branches",
            "uninterrupted versus resumed A0 equivalence",
            "image byte verification against manifest hashes",
        ],
    }
