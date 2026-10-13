"""Approved contract comparison; reuse the eight-request executor unchanged."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.faithbench_monitor_v0.monitor_mechanism_v1 import run_d1

run_d1.OUT = ROOT / 'experiments/faithbench_monitor_v0/private/mechanism_d1b_20261013'

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--self-check' in sys.argv:
        run_d1.self_check()
        run_d1.package()
        print('D1b freeze and eight-request boundary verified')
    else:
        run_d1.main()
