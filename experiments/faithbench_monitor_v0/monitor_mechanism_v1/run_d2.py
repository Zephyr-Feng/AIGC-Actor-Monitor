"""D2 uses the unchanged, exclusive eight-request SSE executor."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.faithbench_monitor_v0.monitor_mechanism_v1 import run_d1

run_d1.OUT = ROOT / 'experiments/faithbench_monitor_v0/private/mechanism_d2_20261013'

if __name__ == '__main__':
    if '--self-check' in sys.argv:
        run_d1.self_check()
        run_d1.package()
        print('D2 frozen eight-request boundary verified')
    else:
        run_d1.main()
