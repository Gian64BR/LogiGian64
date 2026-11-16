import os
from pathlib import Path
import shlex
import sys

target = Path(sys.argv[1]).resolve()
launcher = Path.home()/'.local/bin/logigian64-linux'
if launcher.exists():
    raise SystemExit(f'Ya existe {launcher}; no se reemplazo.')
launcher.write_text('#!/bin/sh\n# LogiGian64 Linux\nexec '+shlex.quote(str(target/'venv/bin/python'))+' '+shlex.quote(str(target/'main.py'))+' "$@"\n')
launcher.chmod(0o755)
from_quote = lambda p: '"'+str(p).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
desktop = Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'applications/logigian64-linux.desktop'
desktop.write_text('[Desktop Entry]\nType=Application\nName=LogiGian64 Linux\nExec='+from_quote(launcher)+'\nIcon='+str(target/'assets/logigian64-logo.png')+'\nTerminal=false\nCategories=Utility;\n')
