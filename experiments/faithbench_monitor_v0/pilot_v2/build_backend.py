"""Compile the pinned backend against existing Ubuntu libraries; no install/model load."""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

COMMIT = "8a1a9b5126126e5228b95fa909d4b08fac65e8b3"


def main():
    root = Path.cwd()
    source = root / "llama-source-b11517"
    if source.exists():
        raise FileExistsError("source already exists; inspect before repeating build")
    url = "https://github.com/ggml-org/llama.cpp"
    env = dict(os.environ, CUDACXX="/usr/local/cuda/bin/nvcc", GIT_TERMINAL_PROMPT="0")
    subprocess.run(["git", "-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=30",
                    "clone", "--depth", "1", "--single-branch", "--branch", "b11517", url, str(source)],
                   env=env, check=True, timeout=120)
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != COMMIT:
        raise ValueError("source tag resolves to unexpected commit")
    configure = ["cmake", "-S", str(source), "-B", str(root / "build-ubuntu22"),
                 "-DCMAKE_BUILD_TYPE=Release", "-DGGML_CUDA=ON", "-DCMAKE_CUDA_ARCHITECTURES=89",
                 "-DGGML_NATIVE=OFF", "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=OFF",
                 "-DLLAMA_CURL=OFF"]
    record = {"commit": COMMIT, "source_url": url,
              "source_tree_commit": head,
              "configure": configure, "gpu_required": False, "system_libraries_changed": False}
    (root / "build_record.json").write_text(json.dumps(record, indent=2) + "\n")
    subprocess.run(configure, env=env, check=True, timeout=180)
    subprocess.run(["cmake", "--build", str(root / "build-ubuntu22"), "--target", "llama-server", "-j4"],
                   env=env, check=True, timeout=1200)
    binary = root / "build-ubuntu22/bin/llama-server"
    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15)
    record.update(binary=str(binary), binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  version_returncode=result.returncode, version_output=result.stdout + result.stderr,
                  completed_unix_time=time.time())
    (root / "build_record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"build_finished": True, "version_returncode": result.returncode,
                      "version_output": result.stdout + result.stderr}), flush=True)
    result.check_returncode()


if __name__ == "__main__":
    main()
