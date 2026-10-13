"""Six bounded range requests, one partial file, final public SHA-256 check."""
import concurrent.futures
import argparse
import json
import os
import time
import threading
import urllib.request
from pathlib import Path
from download_public import FILES, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-log", type=Path)
    args = parser.parse_args()
    name, size, expected, url = FILES[0]
    partial = Path(name + ".accelerated.parallel.part")
    progress = [0] * 6
    if args.resume_log:
        snapshots = [json.loads(line) for line in args.resume_log.read_text().splitlines()
                     if line.startswith('{"received_bytes"')]
        if not snapshots or partial.stat().st_size != size:
            raise ValueError("no valid partial/checkpoint to resume")
        progress = snapshots[-1]["per_range"]
        if len(progress) != 6 or any(not isinstance(n, int) or n < 0 or
                                    n > size*(i+1)//6-size*i//6 for i, n in enumerate(progress)):
            raise ValueError("invalid range checkpoint")
        fd = os.open(partial, os.O_WRONLY)
    else:
        fd = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.ftruncate(fd, size)
    deadline = time.monotonic() + 1500
    cancel = threading.Event()

    def worker(index):
        start = size * index // 6
        end = size * (index + 1) // 6 - 1
        position = start + progress[index]
        if position > end:
            return
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={position}-{end}", "Accept-Encoding": "identity"})
                with urllib.request.urlopen(req, timeout=20) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {position}-{end}/{size}":
                        raise ValueError("server did not honor exact byte range")
                    while position <= end:
                        if cancel.is_set() or time.monotonic() > deadline:
                            raise TimeoutError("download exceeded 25 minute bound")
                        block = response.read1(min(1024 * 1024, end - position + 1))
                        if not block:
                            raise OSError("range ended early")
                        offset = 0
                        while offset < len(block):
                            offset += os.pwrite(fd, block[offset:], position + offset)
                        position += len(block)
                        progress[index] = position - start
                return
            except (OSError, ValueError) as exc:
                print(json.dumps({"range": index, "attempt": attempt, "error": str(exc)}), flush=True)
                if attempt == 2 or time.monotonic() > deadline:
                    raise
        raise RuntimeError("range not completed")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(worker, index) for index in range(6)]
            while not all(future.done() for future in futures):
                failed = [future for future in futures if future.done() and future.exception()]
                if failed:
                    cancel.set()
                    failed[0].result()
                print(json.dumps({"received_bytes": sum(progress), "total_bytes": size, "per_range": progress}), flush=True)
                time.sleep(10)
            for future in futures:
                future.result()
        os.fsync(fd)
    finally:
        os.close(fd)
    if digest(partial) != expected:
        raise ValueError("parallel result SHA-256 mismatch")
    original = Path(name)
    if original.exists():
        original.rename(name + ".single.part")
    partial.rename(original)
    print("Parallel model download verified.", flush=True)
    Path("verified_model_download.json").write_text(json.dumps({"name": name, "size": size,
                                                               "sha256": expected, "url": url}) + "\n")


if __name__ == "__main__":
    main()
