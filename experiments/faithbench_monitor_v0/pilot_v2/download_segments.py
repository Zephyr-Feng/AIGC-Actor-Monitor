"""Resume recorded ranges as small queued segments so one slow connection cannot own GBs."""
import argparse
import concurrent.futures
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from download_public import FILES, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--range-log", type=Path, required=True)
    args = parser.parse_args()
    name, size, expected, url = FILES[0]
    snapshots = [json.loads(line) for line in args.range_log.read_text().splitlines()
                 if line.startswith('{"received_bytes"')]
    initial = snapshots[-1]["per_range"]
    partial = Path(name + ".accelerated.parallel.part")
    if partial.stat().st_size != size or len(initial) != 6:
        raise ValueError("invalid partial/checkpoint")
    segments = []
    for index, received in enumerate(initial):
        start, end = size*index//6, size*(index+1)//6-1
        if not 0 <= received <= end-start+1:
            raise ValueError("invalid received count")
        for position in range(start+received, end+1, 64*1024*1024):
            segments.append({"start": position, "end": min(position+64*1024*1024-1, end), "received": 0})
    fd = os.open(partial, os.O_WRONLY)
    deadline = time.monotonic()+1500
    cancel = threading.Event()

    def worker(segment):
        for attempt in range(3):
            position, end = segment["start"]+segment["received"], segment["end"]
            if position > end:
                return
            if cancel.is_set():
                raise RuntimeError("download canceled")
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={position}-{end}", "Accept-Encoding": "identity"})
                with urllib.request.urlopen(req, timeout=20) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {position}-{end}/{size}":
                        raise ValueError("server did not honor exact range")
                    while position <= end:
                        if cancel.is_set() or time.monotonic() > deadline:
                            raise TimeoutError("download exceeded 25 minute bound")
                        block = response.read1(min(1024*1024, end-position+1))
                        if not block:
                            raise OSError("segment ended early")
                        offset = 0
                        while offset < len(block):
                            offset += os.pwrite(fd, block[offset:], position+offset)
                        position += len(block)
                        segment["received"] = position-segment["start"]
                return
            except (OSError, ValueError) as exc:
                print(json.dumps({"segment_start": segment["start"], "attempt": attempt, "error": str(exc)}), flush=True)
                if attempt == 2 or cancel.is_set() or time.monotonic() > deadline:
                    raise

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(worker, segment) for segment in segments]
            while not all(future.done() for future in futures):
                failed = [future for future in futures if future.done() and future.exception()]
                if failed:
                    cancel.set()
                    failed[0].result()
                record = {"initial_bytes": sum(initial), "segments": segments, "size": size, "sha256": expected}
                Path("download_segment_checkpoint.json").write_text(json.dumps(record)+"\n")
                print(json.dumps({"received_bytes": sum(initial)+sum(s["received"] for s in segments),
                                  "total_bytes": size, "finished_segments": sum(s["received"] == s["end"]-s["start"]+1 for s in segments)}), flush=True)
                time.sleep(10)
            for future in futures:
                future.result()
        os.fsync(fd)
    finally:
        os.close(fd)
    if digest(partial) != expected:
        raise ValueError("download SHA-256 mismatch")
    target = Path(name)
    if target.exists():
        target.rename(name+".single.part")
    partial.rename(target)
    Path("verified_model_download.json").write_text(json.dumps({"name": name, "size": size, "sha256": expected, "url": url})+"\n")
    print("Queued segments complete; full model SHA-256 verified. No model loaded.", flush=True)


if __name__ == "__main__":
    main()
