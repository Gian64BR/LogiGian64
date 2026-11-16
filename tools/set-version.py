"""Synchronize both platforms before building: python tools/set-version.py 0.3.2."""
from pathlib import Path
import re
import sys

root=Path(__file__).resolve().parent.parent
version=sys.argv[1] if len(sys.argv)==2 else ''
if not re.fullmatch(r'\d+\.\d+\.\d+',version):
    raise SystemExit('Uso: python tools/set-version.py MAJOR.MINOR.PATCH')
previous=(root/'VERSION').read_text().strip()
(root/'VERSION').write_text(version+'\n',encoding='utf-8')
for name in ('nexus/__init__.py','linux/nexus/__init__.py'):
    path=root/name
    text=re.sub(r'__version__ = "[^"]+"',f'__version__ = "{version}"',path.read_text(encoding='utf-8-sig'))
    path.write_text(text,encoding='utf-8',newline='\n')
path=root/'version.txt'
text=path.read_text()
components=','.join(version.split('.')+['0'])
text=re.sub(r'(filevers|prodvers)=\([\d,]+\)',lambda m:m[1]+'=('+components+')',text)
text=re.sub(r"(StringStruct\('(?:FileVersion|ProductVersion)', ')[^']+",lambda m:m[1]+version,text)
path.write_text(text,encoding='utf-8')
for name in ('README.md','linux/README-LINUX.md'):
    path=root/name
    path.write_text(path.read_text(encoding='utf-8').replace(previous,version),encoding='utf-8')
print('Windows y Linux:',version)
