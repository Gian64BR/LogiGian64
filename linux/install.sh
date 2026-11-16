#!/bin/sh
set -eu
[ "$(id -u)" -ne 0 ] || { echo 'Instala como usuario normal, sin sudo.' >&2; exit 1; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${XDG_DATA_HOME:-$HOME/.local/share}/logigian64-app
if [ -e "$target" ]; then
    echo "Ya existe $target. Cierra y desinstala esa copia antes de instalar." >&2
    exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "Se necesita Python 3.10 o posterior"'
mkdir -p "$target"
printf 'LogiGian64 Linux source installation\n' > "$target/.logigian64-install"
cp -R "$source_dir/nexus" "$source_dir/assets" "$source_dir/licenses" "$target/"
cp "$source_dir/main.py" "$source_dir/requirements.txt" "$source_dir/LICENSE" "$source_dir/THIRD_PARTY_NOTICES.md" "$target/"
cp -R "$source_dir/tools" "$target/"
python3 -m venv "$target/venv"
"$target/venv/bin/pip" install -r "$target/requirements.txt"
mkdir -p "$HOME/.local/bin" "${XDG_DATA_HOME:-$HOME/.local/share}/applications"
# Python handles shell/desktop quoting, including paths with spaces.
"$target/venv/bin/python" "$source_dir/tools/install-launcher.py" "$target"
echo 'Instalado. Abre LogiGian64 Linux desde el menu de aplicaciones.'
echo "Para habilitar perifericos: sudo bash \"$target/tools/enable-device-access.sh\" \"$USER\""
