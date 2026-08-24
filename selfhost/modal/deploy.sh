#!/bin/bash
# Prepare build context + deploy Omi GPU services (VAD + speaker-ID) to Modal.
# Run from selfhost/modal/. Prereqs: modal CLI installed + `modal token set`.
set -euo pipefail
cd "$(dirname "$0")"

echo "== sync source from backend/ =="
rm -rf src requirements-base.txt requirements-gpu.txt
mkdir -p src
cp ../../backend/modal/*.py src/
cp -r ../../backend/database src/database
cp -r ../../backend/utils src/utils
cp -r ../../backend/models src/models
cp ../../backend/requirements.txt requirements-base.txt
# Inline everything: Modal's builder flattens the requirements file to /, so -r
# references to siblings would not resolve.
grep -v '^-r' ../../backend/modal/requirements.txt > requirements-gpu.txt
cat ../../backend/requirements.txt >> requirements-gpu.txt
# Deviation (documented): torchaudio 2.10 removed AudioMetaData which
# pyannote.audio 3.3.1 imports at module load — pin the 2.8 line instead.
sed -i 's/^torch==2.10.0/torch==2.8.0/; s/^torchaudio==2.10.0/torchaudio==2.8.0/' requirements-gpu.txt
grep -E '^torch|^torchaudio' requirements-gpu.txt
echo "src files: $(find src -name '*.py' | wc -l)"

echo "== deploy =="
modal deploy deploy_omi_gpu.py
