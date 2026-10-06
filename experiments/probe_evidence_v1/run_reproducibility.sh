#!/usr/bin/env bash
set -euo pipefail
export PROBE_EVIDENCE_OUT=/root/autodl-tmp/probe-evidence-v1/output_repeat
export PYTHONPATH=/root/autodl-tmp/probe-evidence-v1/code:/root/autodl-tmp/probe-dinov2-bfree-20261001/deps/probe
cd /root/autodl-tmp/probe-evidence-v1/code
/root/miniconda3/bin/python -u extract_features.py --split eval
/root/miniconda3/bin/python -u check_parity.py
/root/miniconda3/bin/python -u extract_features.py --split reference
/root/miniconda3/bin/python -u build_evidence.py
/root/miniconda3/bin/python -u analyze_evidence.py
