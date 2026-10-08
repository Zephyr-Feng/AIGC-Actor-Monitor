"""Import explicitly reviewed human labels; never infer human labels from agents."""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from render_review import LABELS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_review(record, review):
    status = review.get("review_status")
    if review.get("reviewer_type") != "human" or status not in {"confirmed", "modified", "needs_source", "disputed"}:
        raise ValueError(f"无效人工身份或状态：{record['record_id']}")
    label = review.get("human_label")
    if record["type"] == "trajectory":
        if not isinstance(label, dict) or set(label) != set(LABELS):
            raise ValueError(f"必须具备八项标签：{record['record_id']}")
        values = [(label[field], allowed) for field, allowed in LABELS.items()]
    else:
        values = [(label, LABELS["tool_selection_quality"])]
    # Strict type checks prevent 0/1 silently masquerading as bool.
    if any(not any(type(value) is type(item) and value == item for item in allowed) for value, allowed in values):
        raise ValueError(f"标签枚举无效：{record['record_id']}")
    if status in {"confirmed", "modified"}:
        if review.get("evidence_read") is not True or not str(review.get("human_notes", "")).strip():
            raise ValueError(f"缺少阅读勾选或人工理由：{record['record_id']}")
    try:
        stamp = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("时间缺少时区")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"人工时间无效：{record['record_id']}") from error


def metadata(review):
    return {key: review[key] for key in ["reviewer_type", "review_status", "human_label", "human_notes", "reviewed_at"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--data", type=Path, default=Path(__file__).with_name("review_data.json"))
    parser.add_argument("--lock", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    args.data = args.data.resolve()
    repo_root = Path(__file__).resolve().parents[4]
    data, export = read_json(args.data), read_json(args.reviews)
    if export.get("version") != 1 or export.get("input_fingerprint") != data["input_fingerprint"]:
        raise ValueError("人工导出版本或输入指纹不匹配")
    records = {r["record_id"]: r for r in data["trajectory_records"] + data["call_records"]}
    if len(records) != len(data["trajectory_records"]) + len(data["call_records"]):
        raise ValueError("复核数据有重复 record_id")
    reviews = export.get("records")
    if not isinstance(reviews, dict) or set(reviews) - set(records):
        raise ValueError("人工导出有未知 record_id")
    for rid, review in reviews.items():
        validate_review(records[rid], review)
    lock_path = args.data.parent / "HUMAN_LABEL_LOCK.json"
    existing_lock = read_json(lock_path) if lock_path.exists() else None
    if args.evaluate and not (args.lock or existing_lock):
        raise ValueError("只有标签锁定后才能 --evaluate")
    if args.lock:
        if len(data["trajectory_records"]) != 80:
            raise ValueError("锁定要求恰好80条轨迹")
        missing = []
        for rid in records:
            review = reviews.get(rid, {})
            if review.get("review_status") not in {"confirmed", "modified"}:
                missing.append(rid)
        if missing:
            raise ValueError("尚不能锁定：" + ", ".join(missing))
    def local_path(name):
        path = Path(name)
        return path if path.is_absolute() else repo_root / path
    human_path, call_path = local_path(data["human_audit_path"]), local_path(data["call_audit_path"])
    if existing_lock:
        if existing_lock["input_fingerprint"] != data["input_fingerprint"]:
            raise ValueError("已有锁定文件指纹不匹配")
        if sha(human_path) != existing_lock["human_audit_sha256"] or sha(call_path) != existing_lock["call_audit_sha256"]:
            raise ValueError("锁定后的标签文件已改变")
    # Validate immutable sources; human targets change on subsequent partial imports.
    for name, expected in data.get("source_hashes", {}).items():
        source = local_path(name)
        if source.resolve() not in {human_path.resolve(), call_path.resolve()} and sha(source) != expected:
            raise ValueError("源文件哈希变化，停止导入")
    mapping = read_json(local_path(data["identity_map_path"]))["blind_to_original"]
    human_rows = [json.loads(line) for line in human_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    with call_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns, call_rows = list(reader.fieldnames), list(reader)
    by_key = {(r["sample_id"], r["condition"]): r for r in human_rows}
    if len(by_key) != len(human_rows):
        raise ValueError("原人工轨迹文件有重复key")
    changes, conflicts = [], []
    for rid, review in reviews.items():
        r = records[rid]
        actual = mapping[r["sample_id"]]
        if r["type"] == "trajectory":
            target = by_key[(actual, r["condition"])]
            if review["review_status"] in {"confirmed", "modified"}:
                for field, value in review["human_label"].items():
                    if target.get(field) is not None and target.get(field) != value:
                        conflicts.append(r["sample_id"])
            if target.get("review_status") in {"confirmed", "modified"} and target.get("human_label") != review["human_label"]:
                conflicts.append(r["sample_id"])
        else:
            index = data["call_index"][rid]
            target = call_rows[index["row_index"]]
            expected = (actual, r["condition"], str(index["step"]), str(index["raw_attempt"]))
            found = tuple(target[k] for k in ["sample_id", "condition", "step", "raw_attempt"])
            if found != expected:
                raise ValueError(f"CALL 行索引关联不一致：{rid}")
            if target.get("review_label") and target["review_label"] != review["human_label"]:
                conflicts.append(r["sample_id"])
        if target.get("review_status") in {"confirmed", "modified"} and review["review_status"] not in {"confirmed", "modified"}:
            conflicts.append(r["sample_id"])
        changes.append((r, review, target))
    if conflicts:
        raise ValueError("已有人工标签冲突，未写入：" + ", ".join(sorted(set(conflicts))))
    if existing_lock and any(review["review_status"] not in {"confirmed", "modified"} for _, review, _ in changes):
        raise ValueError("锁定后不能导入缺源或争议状态")
    if existing_lock and not args.lock and sha(args.reviews) != existing_lock["reviews_sha256"]:
        raise ValueError("已有锁定只允许重用完整锁定导出；修改须重新核验 --lock")
    for r, review, target in changes:
        meta = metadata(review)
        if r["type"] == "trajectory":
            target.update(meta)
            if review["review_status"] in {"confirmed", "modified"}:
                target.update(review["human_label"])
                target["notes"] = review["human_notes"]
        else:
            target.update({k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for k, v in meta.items()})
            if review["review_status"] in {"confirmed", "modified"}:
                target["review_label"], target["review_notes"] = review["human_label"], review["human_notes"]
    backup = args.data.parent / "work/backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True, exist_ok=False)
    for path in [human_path, call_path]:
        shutil.copy2(path, backup / (path.stem + "_" + sha(path)[:12] + path.suffix))
    human_tmp = human_path.with_name(human_path.name + ".human-import.tmp")
    call_tmp = call_path.with_name(call_path.name + ".human-import.tmp")
    human_tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in human_rows), encoding="utf-8")
    for name in ["reviewer_type", "review_status", "human_label", "human_notes", "reviewed_at"]:
        if name not in columns:
            columns.append(name)
    with call_tmp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(call_rows)
    human_tmp.replace(human_path)
    call_tmp.replace(call_path)
    if args.lock or existing_lock:
        unassessable_counts = {}
        for record_id, review in reviews.items():
            label = review["human_label"]
            for field, value in (label.items() if isinstance(label, dict) else [("call_label", label)]):
                if value == "unassessable":
                    unassessable_counts[field] = unassessable_counts.get(field, 0) + 1
        lock_path.write_text(json.dumps({"version": 1, "input_fingerprint": data["input_fingerprint"], "locked_at": datetime.now(timezone.utc).isoformat(), "trajectory_human_count": 80, "call_human_count": len(data["call_records"]), "call_scope": "subset risk-review; not 827 independent human annotations", "unassessable_by_field": unassessable_counts, "human_audit_sha256": sha(human_path), "call_audit_sha256": sha(call_path), "reviews_sha256": sha(args.reviews)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已导入 {len(changes)} 条人工状态；备份：{backup}")
    if args.evaluate:
        evaluator = Path(__file__).parent.parent / "evaluate_b0_d.py"
        try:
            subprocess.run([sys.executable, str(evaluator)], cwd=evaluator.parents[3], check=True)
        finally:
            # The evaluator rewrites away metadata. Restore reviewed files even
            # if evaluation exits with an error; the labels remain identical.
            human_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in human_rows), encoding="utf-8")
            with call_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(call_rows)
        print("已运行解盲评价并保留人工复核元数据；gate 决策仍需按人审范围讨论。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, IndexError) as error:
        sys.exit(str(error))
