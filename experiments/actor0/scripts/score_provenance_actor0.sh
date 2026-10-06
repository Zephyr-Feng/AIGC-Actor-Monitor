#!/usr/bin/env bash
set -euo pipefail

RUN=/root/autodl-tmp/actor0-bfree-20261002
CODE="$RUN/code/actor0"
TOOLBOX=/root/autodl-tmp/toolbox_screening
PY=/root/miniconda3/bin/python

C2PA_BIN="$TOOLBOX/bin/c2patool-v0.28.1/c2patool/c2patool"
GLIBC_ROOT="$TOOLBOX/bin/runtime-glibc239/root"
LOADER="$GLIBC_ROOT/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"
LIBS="$GLIBC_ROOT/usr/lib/x86_64-linux-gnu"
WRAPPER="$RUN/bin/c2patool_glibc239.sh"
mkdir -p "$RUN/bin" "$RUN/logs" "$RUN/scores"
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
exec "$LOADER" --library-path "$LIBS:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu" "$C2PA_BIN" "\$@"
EOF
chmod 755 "$WRAPPER"
"$WRAPPER" --version

"$PY" "$CODE/scripts/score_provenance_actor0.py" \
  --manifest "$RUN/manifests/actor0_all_manifest.jsonl" \
  --image-root "$RUN/data" \
  --c2patool "$WRAPPER" \
  --exiftool "$TOOLBOX/bin/exiftool-13.59/exiftool" \
  --run-root "$RUN/scores/provenance" \
  --expected-count 480 \
  --positive-control-status sample_C_parsed_one_manifest_signature_untrusted \
  2>&1 | tee "$RUN/logs/score_provenance.log"
