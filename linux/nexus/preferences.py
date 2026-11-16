"""XDG autostart; no registry or system-wide startup changes."""
import os
from pathlib import Path
import sys

def _file():
    return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'autostart/logigian64.desktop'

def startup_enabled():
    path=_file()
    return path.is_file() and 'Hidden=true' not in path.read_text(encoding='utf-8')

def _quote(value):
    return '"'+str(value).replace('%', '%%').replace(chr(92),chr(92)*2).replace('"',chr(92)+'"').replace('`',chr(92)+'`').replace('$',chr(92)+'$')+'"'

def set_startup(enabled):
    path=_file()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    command=[sys.executable]
    if not getattr(sys,'frozen',False):command.append(str(Path(__file__).resolve().parent.parent/'main.py'))
    command.append('--startup')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('[Desktop Entry]\nType=Application\nName=LogiGian64\nExec='+ ' '.join(_quote(p) for p in command)+'\nTerminal=false\nX-GNOME-Autostart-enabled=true\n',encoding='utf-8')
