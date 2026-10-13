"""Unpack official Ubuntu libraries locally; never install/replace system packages."""
import hashlib
import argparse
import json
import subprocess
from pathlib import Path

PACKAGES = [
    ("libc6_2.39-0ubuntu8.9_amd64.deb", "g/glibc",
     "ff5557d99b51f761c4b7c92368b9cc45565eda17df9bf9eb4b134d09825008be"),
    ("libstdc++6_14.2.0-4ubuntu2~24.04.1_amd64.deb", "g/gcc-14",
     "a51f8de7829211db961a31f02158058ad1a95f92ac6d0a5dff6350e2821c54c0"),
    ("libgcc-s1_14.2.0-4ubuntu2~24.04.1_amd64.deb", "g/gcc-14",
     "aa7fadbe33b78bcf99885318040601c550c208929565b179891d9a3cc2aa68cd"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-host", choices=("security.ubuntu.com", "archive.ubuntu.com"), default="security.ubuntu.com")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    destination = root / "runtime-noble"
    records = []
    for name, folder, expected in PACKAGES:
        url = f"https://{args.download_host}/ubuntu/pool/main/{folder}/{name}"
        target = root / name
        if not (target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected):
            subprocess.run(["curl", "-fL", "--connect-timeout", "8", "--max-time", "45", "--output", str(target), url],
                           check=True, timeout=50)
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("official package SHA-256 mismatch: " + name)
        subprocess.run(["dpkg-deb", "--extract", str(target), str(destination)], check=True, timeout=20)
        records.append({"name": name, "url": url, "sha256": actual, "bytes": target.stat().st_size})
        print(json.dumps({"verified_and_unpacked": name}), flush=True)
    loader = next(p for p in destination.rglob("ld-linux-x86-64.so.2") if not p.is_symlink())
    binary = root / "runtime/llama-b11517/llama-server"
    libraries = [loader.parent, root / "runtime/llama-b11517",
                 root / "runtime/cudart-llama-b11517-bin-ubuntu-cuda-12.8-x64",
                 Path("/usr/lib/x86_64-linux-gnu")]
    argv = [str(loader), "--library-path", ":".join(str(p) for p in libraries), str(binary)]
    result = subprocess.run(argv+["--version"], capture_output=True, text=True, timeout=15)
    record = {"packages": records, "backend_argv": argv, "system_libraries_changed": False,
              "model_loaded": False, "returncode": result.returncode, "output": result.stdout+result.stderr}
    (root / "private_libraries_record.json").write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps({"returncode": result.returncode, "output": result.stdout+result.stderr}), flush=True)
    result.check_returncode()


if __name__ == "__main__":
    main()
