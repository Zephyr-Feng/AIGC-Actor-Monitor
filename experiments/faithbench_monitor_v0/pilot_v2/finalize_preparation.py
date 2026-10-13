"""Assemble verified deployment receipts and a GPU launch plan; no launch/inference."""
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    model = json.loads((root / "verified_model_download.json").read_text())
    runtime = json.loads((root / "verified_runtime_downloads.json").read_text())
    libraries = json.loads((root / "private_libraries_record.json").read_text())
    pilot = root.parent / "monitor-pilot-20261009"
    preflight_path = pilot / "outputs/preflight_27b_20261009_v2/token_preflight.json"
    preflight = json.loads(preflight_path.read_text())
    if libraries["returncode"] != 0 or len(preflight["cases"]) != 8 or not all(
            case["within_planned_context"] for case in preflight["cases"]):
        raise ValueError("preparation validation incomplete")
    weight_path = root / model["name"]
    if weight_path.stat().st_size != model["size"]:
        raise ValueError("weight size changed")
    (root / "verified_downloads.json").write_text(json.dumps([model]+runtime, indent=2)+"\n")
    prefix = libraries["backend_argv"]
    server_argv = prefix + ["-m", str(weight_path), "--n-gpu-layers", "99", "--ctx-size", "24576",
                            "--parallel", "1", "--host", "127.0.0.1", "--port", "8089",
                            "--chat-template-kwargs", '{"enable_thinking":false}', "--reasoning", "off",
                            "--flash-attn", "on", "--batch-size", "512", "--ubatch-size", "256"]
    runner_argv = ["/root/autodl-tmp/mini-faithbench-v0/actor-venv/bin/python", "-u",
                   str(pilot / "experiments/faithbench_monitor_v0/pilot_v2/run.py"),
                   "--input-dir", str(pilot / "experiments/faithbench_monitor_v0/private/pilot_v2_locked"),
                   "--backend", "llama_27b", "--model-dir", str(weight_path),
                   "--output-dir", str(pilot / "outputs/text_review_v2_27b_20261009"), "--run-inference"]
    gpu = subprocess.run(["nvidia-smi", "--list-gpus"], capture_output=True, text=True, timeout=10)
    record = {"status": "prepared_no_inference", "model": model, "backend_packages": runtime,
              "private_libraries": libraries, "backend_binary_sha256": hashlib.sha256(Path(prefix[-1]).read_bytes()).hexdigest(),
              "token_preflight_sha256": hashlib.sha256(preflight_path.read_bytes()).hexdigest(),
              "max_input_plus_output": max(c["input_plus_max_output"] for c in preflight["cases"]),
              "server_argv": server_argv, "runner_argv": runner_argv,
              "gpu_probe_returncode": gpu.returncode, "gpu_probe_output": gpu.stdout+gpu.stderr,
              "weight_tensors_loaded": False, "generation_executed": False,
              "training_executed": False, "actor_actions_executed": False}
    (root / "deployment_prepared_20261009.json").write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps({"status": record["status"], "cases": 8, "max_input_plus_output": record["max_input_plus_output"],
                      "gpu": gpu.stdout+gpu.stderr, "generation_executed": False}), flush=True)


if __name__ == "__main__":
    main()
