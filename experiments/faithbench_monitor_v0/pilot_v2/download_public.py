"""Bounded, resumable public downloads. Run in a new isolated directory."""
import hashlib
import argparse
import json
import subprocess
import tarfile
from pathlib import Path

FILES = [
    ("Qwen3.5-27B-Q4_K_M.gguf", 16740812704,
     "84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806",
     "https://huggingface.co/unsloth/Qwen3.5-27B-GGUF/resolve/3221f178a6b842d04f1fb42f1c413534adcc0a6a/Qwen3.5-27B-Q4_K_M.gguf"),
    ("llama-b11517-bin-ubuntu-cuda-12.8-x64.tar.gz", 171981006,
     "10565a6a0c231ea10625ff7de128c0c6ee65e8dab60f59b88f5d5a1f8e028e91",
     "https://github.com/ggml-org/llama.cpp/releases/download/b11517/llama-b11517-bin-ubuntu-cuda-12.8-x64.tar.gz"),
    ("cudart-llama-b11517-bin-ubuntu-cuda-12.8-x64.tar.gz", 594377950,
     "5be78009a9d636e50f2caefc1b18c613a58ab698fe5655f0b950ee9d2c6f8f6a",
     "https://github.com/ggml-org/llama.cpp/releases/download/b11517/cudart-llama-b11517-bin-ubuntu-cuda-12.8-x64.tar.gz"),
]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    verified = []
    for name, size, expected, url in (FILES[1:] if args.runtime_only else FILES):
        target = root / name
        print(json.dumps({"starting": name, "existing_bytes": target.stat().st_size if target.exists() else 0}), flush=True)
        if not (target.exists() and target.stat().st_size == size and digest(target) == expected):
            subprocess.run(["curl", "-fL", "--connect-timeout", "15", "--max-time", "1800",
                            "--speed-limit", "1024", "--speed-time", "60", "--retry", "1",
                            "--continue-at", "-", "--output", str(target), url], check=True)
        if target.stat().st_size != size or digest(target) != expected:
            raise ValueError("public download size or SHA-256 mismatch: " + name)
        verified.append({"name": name, "size": size, "sha256": expected, "url": url})
        print(json.dumps({"verified": name}), flush=True)
    for name, *_ in FILES[1:]:
        with tarfile.open(root / name) as archive:
            archive.extractall(root / "runtime", filter="data")
    record_name = "verified_runtime_downloads.json" if args.runtime_only else "verified_downloads.json"
    (root / record_name).write_text(json.dumps(verified, indent=2) + "\n")
    print("All public downloads verified; no model loaded.", flush=True)


if __name__ == "__main__":
    main()
