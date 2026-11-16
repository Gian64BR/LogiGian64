"""Collect the licenses of the actual Linux build dependencies."""
from importlib.metadata import distribution
from pathlib import Path
import sys

root=Path(__file__).resolve().parent.parent
versions=[]
for name in ('evdev','pyudev','pyinstaller','hidapi','PySide6','shiboken6'):
    dist=distribution(name)
    versions.append(f'{name}=={dist.version}')
    for item in dist.files or []:
        if Path(item).name.upper().startswith(('LICENSE','COPYING')):
            source=Path(dist.locate_file(item))
            if source.is_file():
                (root/'licenses'/f'{name}-{source.name}').write_bytes(source.read_bytes())
for source in (Path(sys.base_prefix)/'lib/python3.12/LICENSE.txt',Path('/usr/lib/python3.12/LICENSE.txt')):
    if source.is_file():
        (root/'licenses/Python-LICENSE.txt').write_bytes(source.read_bytes());break
(root/'qa/build-dependencies.txt').write_text('\n'.join(versions)+'\n')
