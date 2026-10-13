"""Run the frozen three-request trial once; preserve CPU and model provenance."""
import json
import os
import sys
from pathlib import Path

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(0, str(Path(__file__).parent))
import pilot


def protection():
    expected = json.loads((pilot.PRIVATE / 'expected_protection.json').read_text())
    actual = {}
    for name, value in expected.items():
        path = Path(name)
        actual[name] = {'size': path.stat().st_size, 'sha256': pilot.sha256(path)}
        assert actual[name] == value, name
    return actual


def main():
    import torch
    import transformers
    torch.set_num_threads(2)
    assert torch.__version__ == '2.12.1+cu130' and transformers.__version__ == '4.57.4'
    assert torch.cuda.is_available()
    package = pilot.verify(pilot.PRIVATE)
    expected = json.loads((pilot.PRIVATE / 'cpu_preflight.json').read_text())
    base = Path(expected['base'])
    assert not (pilot.ROOT / 'output').exists()
    before = protection()
    pilot.dump(pilot.ROOT / 'protection_before.json', before)
    print('protection before verified', flush=True)
    actual, _, _ = pilot.cpu_check(package, base,
        lambda key: (pilot.PRIVATE / package['assets'][key]['file']).read_bytes())
    for key in ['branches', 'input_ids_sha256', 'processor_assets', 'blinded_pre_stop_tokens']:
        assert actual[key] == expected[key], key
    pilot.dump(pilot.ROOT / 'deployment_preflight.json', actual)
    print('deployed CPU inputs match frozen preflight', flush=True)
    pilot.execute(pilot.PRIVATE, base, pilot.ROOT / 'output')
    pilot.dump(pilot.ROOT / 'protection_after.json', protection())
    pilot.dump(pilot.ROOT / 'worker_completed.json', {'requests': 3, 'protection_verified': len(before)})
    print('worker completed', flush=True)


if __name__ == '__main__':
    main()
