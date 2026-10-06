#!/usr/bin/env python3
"""Inspect C2PA and image metadata without treating metadata absence as fake."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
from pathlib import Path

from PIL import Image


FIELDS = [
    "path", "sample_id", "source_group_id", "ground_truth", "generator",
    "c2pa_present", "c2pa_valid", "c2pa_trusted", "c2pa_validation_status",
    "digital_source_type", "generator_claim", "software_agent",
    "exif_present", "camera_make", "camera_model", "software", "datetime_original",
    "xmp_present", "iptc_present", "image_format", "width", "height",
    "camera_metadata_present", "software_metadata_present",
    "provenance_evidence_type", "provenance_strength", "actionable", "notes",
    "c2patool_exit_code", "exiftool_exit_code", "seconds", "unified_output_json",
]


def read_manifest(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def walk_pairs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from walk_pairs(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_pairs(item)


def find_values(value, wanted: set[str]) -> list[str]:
    found = []
    for key, item in walk_pairs(value):
        if key.casefold() in wanted and isinstance(item, (str, int, float)):
            text = str(item).strip()
            if text and text not in found:
                found.append(text)
    return found


def find_named(value, patterns: tuple[str, ...]) -> list[str]:
    found = []
    for key, item in walk_pairs(value):
        normalized = re.sub(r"[^a-z]", "", key.casefold())
        if any(pattern in normalized for pattern in patterns) and isinstance(item, (str, int, float)):
            text = str(item).strip()
            if text and text not in found:
                found.append(text)
    return found


def bool_cell(value: bool | None) -> str:
    return "" if value is None else int(value)


def parse_manifest_report(payload):
    if not isinstance(payload, (dict, list)):
        return False, None, None, "", "", ""
    all_pairs = list(walk_pairs(payload))
    manifest_nodes = []
    if isinstance(payload, dict):
        manifests = payload.get("manifests")
        if isinstance(manifests, dict):
            manifest_nodes.extend(manifests.values())
        if payload.get("active_manifest"):
            manifest_nodes.append(payload)
    present = bool(manifest_nodes or find_values(payload, {"active_manifest", "claim_generator", "claimgenerator"}))
    statuses = []
    status_fields_seen = False
    for key, value in all_pairs:
        if key.casefold() == "validation_status":
            status_fields_seen = True
            if isinstance(value, list):
                statuses.extend(value)
            elif value:
                statuses.append(value)
    status_strings = []
    for item in statuses:
        if isinstance(item, dict):
            code = item.get("code") or item.get("label") or item.get("url") or item.get("type")
            explanation = item.get("explanation") or item.get("description") or item.get("message")
            text = ": ".join(str(part) for part in (code, explanation) if part)
            status_strings.append(text or json.dumps(item, ensure_ascii=False, sort_keys=True))
        else:
            status_strings.append(str(item))
    status_text = "; ".join(dict.fromkeys(status_strings))

    lowered = status_text.casefold()
    invalid_markers = ("assertion.datahash.mismatch", "assertion.bmffhash.mismatch", "claim.signature.mismatch",
                       "claim.signature.invalid", "ingredient.hash.mismatch", "hardbinding")
    untrusted_markers = ("untrusted", "not trusted", "trust anchor", "signingcredential.untrusted")
    if not present:
        valid = False
    elif any(marker in lowered for marker in invalid_markers):
        valid = False
    elif status_fields_seen:
        # The positive-control run checks this interpretation against the official tool's
        # output for a valid signed asset and a byte-tampered signed asset.
        valid = True
    else:
        valid = None
    trusted = False if any(marker in lowered for marker in untrusted_markers) else None
    if trusted is None:
        trust_values = [str(item).casefold() for item in find_named(payload, ("trusted", "truststatus", "validationstatus"))]
        if any(item in {"true", "trusted", "valid"} for item in trust_values):
            trusted = True
        elif any("untrusted" in item for item in trust_values):
            trusted = False

    source_types = find_named(payload, ("digitalsourcetype",))
    generators = find_named(payload, ("claimgenerator", "claimgeneratorinfo", "generatorclaim"))
    software_agents = find_named(payload, ("softwareagent",))
    generator_claim = "; ".join(dict.fromkeys(source_types + generators))
    return present, valid, trusted, status_text, generator_claim, "; ".join(dict.fromkeys(software_agents))


def run_json_command(command: list[str], timeout: int):
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    stdout = completed.stdout.strip()
    parsed = None
    parse_error = ""
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            parse_error = f"stdout is not valid JSON: {exc}"
    return completed, parsed, parse_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--c2patool", required=True, help="Official c2patool binary path or PATH command")
    parser.add_argument("--exiftool", required=True, help="ExifTool binary path or PATH command")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--allow-c2patool-unavailable", action="store_true",
                        help="Continue EXIF/XMP/IPTC extraction if c2patool cannot start; C2PA fields remain unknown")
    parser.add_argument("--positive-control-status", default="not_run",
                        help="Record the prespecified official C2PA control outcome")
    parser.add_argument("--expected-count", type=int, default=300)

    args = parser.parse_args()

    records = read_manifest(args.manifest)
    if len(records) != args.expected_count:
        raise ValueError(f"expected {args.expected_count} frozen images, got {len(records)}")
    run_root = args.run_root.resolve()
    output_csv = run_root / "provenance_results.csv"
    raw_jsonl = run_root / "raw" / "provenance_raw.jsonl"
    config_path = run_root / "raw" / "config.json"
    if any(path.exists() for path in (output_csv, raw_jsonl, config_path)):
        raise FileExistsError("Refusing to overwrite provenance outputs")
    raw_jsonl.parent.mkdir(parents=True, exist_ok=True)

    version_records = {}
    c2patool_available = True
    for name, command in (("c2patool", [args.c2patool, "--version"]), ("exiftool", [args.exiftool, "-ver"])):
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=args.timeout_seconds, check=False)
            version_records[name] = {"exit_code": result.returncode, "stdout": result.stdout.strip(),
                                     "stderr": result.stderr.strip()}
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"exit code {result.returncode}")
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            version_records[name] = {"exit_code": getattr(locals().get("result"), "returncode", None),
                                     "stdout": getattr(locals().get("result"), "stdout", "").strip(),
                                     "stderr": getattr(locals().get("result"), "stderr", "").strip(),
                                     "error": str(exc)}
            if name == "c2patool" and args.allow_c2patool_unavailable:
                c2patool_available = False
            else:
                raise RuntimeError(f"Cannot verify {name} version: {exc}") from exc
    config = {
        "tool": "ProvenanceInspector",
        "manifest": str(args.manifest.resolve()),
        "c2patool_version": version_records["c2patool"]["stdout"],
        "exiftool_version": version_records["exiftool"]["stdout"],
        "c2pa_command": "c2patool <image> (official default manifest JSON report; no test-label decisions)",
        "metadata_command": "exiftool -j -G1 -a -s -n -EXIF:all -XMP:all -IPTC:all -PNG:all -File:all <image>",
        "trust_policy": "Record trust as unknown unless c2patool output explicitly establishes it; no absence-of-metadata inference.",
        "positive_control_required": True,
        "c2patool_available": c2patool_available,
        "positive_control_status": args.positive_control_status,
        "c2pa_scan_status": "running" if c2patool_available else "unavailable_before_scan",
    }
    write_json(config_path, config)

    rows = []
    start_all = time.perf_counter()
    failures = 0
    with raw_jsonl.open("x", encoding="utf-8") as raw_stream:
        with output_csv.open("x", newline="", encoding="utf-8") as csv_stream:
            writer = csv.DictWriter(csv_stream, fieldnames=FIELDS)
            writer.writeheader()
            for index, record in enumerate(records, start=1):
                started = time.perf_counter()
                image_path = (args.image_root / record["relative_path"]).resolve()
                if not image_path.is_file():
                    raise FileNotFoundError(image_path)

                c2pa_result = {"exit_code": None, "stdout": "", "stderr": "", "json": None, "error": ""}
                exif_result = {"exit_code": None, "stdout": "", "stderr": "", "json": None, "error": ""}
                if c2patool_available:
                    try:
                        completed, c2pa_payload, parse_error = run_json_command(
                            [args.c2patool, str(image_path)], args.timeout_seconds)
                        c2pa_result = {"exit_code": completed.returncode, "stdout": completed.stdout,
                                       "stderr": completed.stderr, "json": c2pa_payload, "error": parse_error}
                        present, valid, trusted, validation_status, generator_claim, software_agent = parse_manifest_report(c2pa_payload)
                        if completed.returncode != 0:
                            c2pa_result["error"] = (c2pa_result["error"] + "; " if parse_error else "") + completed.stderr.strip()
                            lowered_error = completed.stderr.casefold()
                            if not any(marker in lowered_error for marker in (
                                    "no manifest", "no active manifest", "manifest store not found", "no claim found")):
                                failures += 1
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        present, valid, trusted, validation_status, generator_claim, software_agent = None, None, None, "TOOL_ERROR", "", ""
                        c2pa_result["error"] = str(exc)
                        failures += 1
                else:
                    present, valid, trusted, validation_status, generator_claim, software_agent = None, None, None, "TOOL_UNAVAILABLE", "", ""
                    c2pa_result["error"] = version_records["c2patool"].get("error", "c2patool could not start")
                    failures += 1

                try:
                    completed, exif_payload, parse_error = run_json_command([
                        args.exiftool, "-j", "-G1", "-a", "-s", "-n", "-EXIF:all", "-XMP:all",
                        "-IPTC:all", "-PNG:all", "-File:all", str(image_path)], args.timeout_seconds)
                    exif_result = {"exit_code": completed.returncode, "stdout": completed.stdout,
                                   "stderr": completed.stderr, "json": exif_payload, "error": parse_error}
                    if completed.returncode != 0 or not isinstance(exif_payload, list) or len(exif_payload) != 1:
                        failures += 1
                        metadata = {}
                    else:
                        metadata = exif_payload[0]
                except subprocess.TimeoutExpired as exc:
                    metadata = {}
                    exif_result["error"] = f"timeout after {args.timeout_seconds}s"
                    failures += 1

                tags = {str(key): value for key, value in metadata.items()}
                exif_tags = {key: value for key, value in tags.items() if key.startswith("EXIF:")}
                xmp_tags = {key: value for key, value in tags.items() if key.startswith("XMP:")}
                iptc_tags = {key: value for key, value in tags.items() if key.startswith(("IPTC:", "Photoshop:"))}
                make = tags.get("EXIF:Make", "")
                camera_model = tags.get("EXIF:Model", "")
                software_values = [value for key, value in tags.items()
                                   if key.rsplit(":", 1)[-1].casefold() in {"software", "creatortool", "processingsoftware", "producer"}
                                   and value not in (None, "")]
                software = "; ".join(dict.fromkeys(str(value) for value in software_values))
                datetime_original = tags.get("EXIF:DateTimeOriginal", "")
                time_values = [value for key, value in tags.items()
                               if key.rsplit(":", 1)[-1].casefold() in {"datetimeoriginal", "datetimecreated", "datecreated", "createdate"}
                               and value not in (None, "")]
                creator_values = [value for key, value in tags.items()
                                  if key.rsplit(":", 1)[-1].casefold() in {"artist", "creator", "by-line", "copyright"}
                                  and value not in (None, "")]
                try:
                    with Image.open(image_path) as image:
                        image_format, width, height = image.format or "", image.width, image.height
                except Exception as exc:
                    image_format, width, height = "", "", ""
                    exif_result["image_read_error"] = str(exc)

                safe_sample_id = record["sample_id"].replace(":", "_")
                c2pa_result["path"] = str(run_root / "raw" / "c2pa" / f"{safe_sample_id}.json")
                exif_result["path"] = str(run_root / "raw" / "exiftool" / f"{safe_sample_id}.json")
                write_json(Path(c2pa_result["path"]), c2pa_result)
                write_json(Path(exif_result["path"]), exif_result)
                c2pa_present = bool(present)
                exif_present = bool(exif_tags)
                xmp_present = bool(xmp_tags)
                iptc_present = bool(iptc_tags)
                camera_present = bool(make or camera_model)
                software_present = bool(software or software_agent or find_named(c2pa_result.get("json"), ("softwareagent",)))
                source_types = find_named(c2pa_result.get("json"), ("digitalsourcetype",))
                actionable = bool(c2pa_present or camera_present or software_present or time_values or creator_values or source_types)
                if c2pa_present and valid and trusted and source_types:
                    strength = "strong"
                    evidence_type = "trusted_c2pa_claim"
                elif c2pa_present and source_types:
                    strength = "moderate" if valid else "weak"
                    evidence_type = "c2pa_source_claim"
                elif camera_present:
                    strength, evidence_type = "weak", "camera_metadata"
                elif software_present:
                    strength, evidence_type = "weak", "software_metadata"
                elif exif_present or xmp_present or iptc_present:
                    strength, evidence_type = "none", "metadata_present_non_actionable"
                    actionable = False
                else:
                    strength, evidence_type = "none", "none"
                    actionable = False

                lowered_claim = " ".join(source_types).casefold()
                if c2pa_present and valid and trusted and "trainedalgorithmicmedia" in lowered_claim:
                    verdict = "fake"
                elif c2pa_present and valid and trusted and "digitalcapture" in lowered_claim:
                    verdict = "real"
                else:
                    verdict = "inconclusive"
                if not c2patool_available:
                    notes = "C2PA was not evaluated because the official parser could not start; metadata absence or non-origin-bearing tags are inconclusive about origin."
                    observation = "C2PA status is unknown; EXIF/XMP/IPTC metadata was extracted without inferring origin."
                elif not actionable:
                    notes = "No positive provenance evidence is available; metadata absence or non-origin-bearing tags are inconclusive about origin."
                    observation = "No C2PA claim or usable origin-bearing metadata was found."
                else:
                    notes = "Metadata and C2PA claims are recorded as evidence; claims are not treated as authoritative unless explicitly trusted."
                    observation = "; ".join(part for part in (
                        f"C2PA present (valid={valid}, trusted={trusted})" if c2pa_present else "",
                        f"source type: {', '.join(source_types)}" if source_types else "",
                        f"camera: {make} {camera_model}".strip() if camera_present else "",
                        f"software: {software}" if software else "",
                    ) if part) or "Metadata is present but does not establish image origin."
                unified = {
                    "tool": "ProvenanceInspector", "evidence_type": evidence_type,
                    "verdict": verdict, "score": None, "strength": strength,
                    "observation": observation,
                    "limitations": ("C2PA parser was unavailable. Metadata can be absent, stripped, or forged; claims not verified by the parser do not establish origin."
                                    if not c2patool_available else
                                    "Metadata can be absent, stripped, or forged; untrusted claims do not establish origin."),
                }
                row = {
                    "path": str(image_path), "sample_id": record["sample_id"],
                    "source_group_id": record["source_group"], "ground_truth": int(record["label_id"]),
                    "generator": record["generator"], "c2pa_present": bool_cell(present),
                    "c2pa_valid": bool_cell(valid), "c2pa_trusted": bool_cell(trusted),
                    "c2pa_validation_status": validation_status,
                    "digital_source_type": "; ".join(dict.fromkeys(source_types)),
                    "generator_claim": generator_claim, "software_agent": software_agent,
                    "exif_present": int(exif_present), "camera_make": make, "camera_model": camera_model,
                    "software": software, "datetime_original": datetime_original,
                    "xmp_present": int(xmp_present), "iptc_present": int(iptc_present),
                    "image_format": image_format, "width": width, "height": height,
                    "camera_metadata_present": int(camera_present), "software_metadata_present": int(software_present),
                    "provenance_evidence_type": evidence_type, "provenance_strength": strength,
                    "actionable": int(actionable), "notes": notes,
                    "c2patool_exit_code": c2pa_result.get("exit_code"),
                    "exiftool_exit_code": exif_result.get("exit_code"),
                    "seconds": round(time.perf_counter() - started, 6),
                    "unified_output_json": json.dumps(unified, ensure_ascii=False, separators=(",", ":")),
                }
                writer.writerow(row)
                csv_stream.flush()
                raw_stream.write(json.dumps({"sample_id": record["sample_id"], "c2pa": c2pa_result,
                                            "exiftool": exif_result, "row": row}, ensure_ascii=False) + "\n")
                raw_stream.flush()
                rows.append(row)
                print(f"image={index}/{len(records)} sample_id={record['sample_id']} actionable={row['actionable']} failures={failures}", flush=True)

    runtime = {"images": len(rows), "tool_errors": failures,
               "total_seconds": time.perf_counter() - start_all,
               "seconds_per_image": (time.perf_counter() - start_all) / max(len(rows), 1)}
    write_json(run_root / "raw" / "runtime.json", runtime)
    config["c2pa_scan_status"] = "completed" if failures == 0 else "completed_with_tool_errors"
    config["images_scanned"] = len(rows)
    config["tool_errors"] = failures
    write_json(config_path, config)
    print(json.dumps(runtime, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
