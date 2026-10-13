"""Inspect GGUF metadata and vocabulary only. Never load tensors or generate."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    libraries = json.loads((root / "private_libraries_record.json").read_text())
    if libraries["returncode"] != 0:
        raise ValueError("backend compatibility check failed")
    verified = json.loads((root / "verified_model_download.json").read_text())
    model = root / verified["name"]
    if (verified["sha256"] != "84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806"
            or model.stat().st_size != verified["size"]):
        raise ValueError("weight download is not verified")
    sys.path.insert(0, str(root / "llama-source-b11517/gguf-py"))
    from gguf import GGUFReader
    from jinja2.sandbox import SandboxedEnvironment
    reader = GGUFReader(model)
    template_text = reader.fields["tokenizer.chat_template"].contents()
    architecture = reader.fields["general.architecture"].contents()
    environment = SandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)

    def raise_exception(message):
        raise ValueError(message)

    environment.globals["raise_exception"] = raise_exception
    template = environment.from_string(template_text)
    inputs = root.parent / "monitor-pilot-20261009/experiments/faithbench_monitor_v0/private/pilot_v2_locked"
    manifest = json.loads((inputs / "manifest.json").read_text())
    if hashlib.sha256((inputs / "manifest.json").read_bytes()).hexdigest() != "a0cea96066cc0b20f25e5dd57e1b5489b6a302dd6ac720774760016f85b23a17":
        raise ValueError("v2 manifest changed")
    output = root.parent / "monitor-pilot-20261009/outputs/preflight_27b_20261009_v2"
    output.mkdir(exist_ok=False)
    prefix = libraries["backend_argv"][:-1] + [str(root / "runtime/llama-b11517/llama-tokenize")]
    rows = []
    for cid in manifest["case_ids"]:
        request_file = inputs / f"{cid}_request.txt"
        if hashlib.sha256(request_file.read_bytes()).hexdigest() != manifest["artifact_hashes"][request_file.name]:
            raise ValueError("request changed")
        request = request_file.read_text()
        rendered = template.render(messages=[{"role": "user", "content": request}],
                                   add_generation_prompt=True, enable_thinking=False)
        prompt_file = output / f"{cid}_chat.txt"
        prompt_file.write_bytes(rendered.encode())
        result = subprocess.run(prefix + ["-m", str(model), "-f", str(prompt_file), "--ids",
                                          "--show-count", "--no-escape"],
                                capture_output=True, text=True, timeout=60)
        (output / f"{cid}_tokenizer.log").write_text(result.stderr)
        result.check_returncode()
        match = re.search(r"Total number of tokens: (\d+)", result.stdout)
        if not match:
            raise ValueError("tokenizer did not report count")
        count = int(match.group(1))
        rows.append({"case_id": cid, "input_tokens": count, "input_plus_max_output": count+4096,
                     "within_planned_context": count+4096 <= 24576,
                     "rendered_sha256": hashlib.sha256(prompt_file.read_bytes()).hexdigest()})
        print(json.dumps({"completed": len(rows), "input_tokens": count}), flush=True)
    record = {"cases": rows, "architecture": architecture,
              "chat_template_sha256": hashlib.sha256(template_text.encode()).hexdigest(),
              "chat_template_renderer": "Python Jinja2; native server rendering still requires GPU-run verification",
              "thinking_enabled": False, "planned_context": 24576,
              "input_manifest_sha256": hashlib.sha256((inputs / "manifest.json").read_bytes()).hexdigest(),
              "vocabulary_only": True, "weight_tensors_loaded": False, "generation_executed": False,
              "actor_actions_executed": False, "images_supplied": 0}
    (output / "token_preflight.json").write_text(json.dumps(record, indent=2)+"\n")
    if not all(row["within_planned_context"] for row in rows):
        raise ValueError("a request exceeds planned context")
    print(json.dumps({"preflight_valid": True, "cases": len(rows),
                      "max_input_plus_output": max(row["input_plus_max_output"] for row in rows),
                      "weight_tensors_loaded": False, "generation_executed": False}), flush=True)


if __name__ == "__main__":
    main()
