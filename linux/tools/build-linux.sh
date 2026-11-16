#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p qa
python_bin=${PYTHON:-/opt/logigian64-build/bin/python}
"$python_bin" tools/collect-licenses.py
"$python_bin" -m PyInstaller --noconfirm --clean LogiGian64-linux.spec > qa/build.log 2>&1
"$python_bin" tools/package-linux.py
