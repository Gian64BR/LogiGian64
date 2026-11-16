"""Prepare a single release, requiring matching Windows and Linux packages."""
from pathlib import Path
import ast
import hashlib
import json
import re
import shutil
import tarfile
import zipfile

root=Path(__file__).resolve().parent.parent
version=(root/'VERSION').read_text().strip()
for path in (root/'nexus/__init__.py',root/'linux/nexus/__init__.py'):
    match=re.search(r'__version__ = ("[^"]+")',path.read_text(encoding='utf-8'))
    assert match and ast.literal_eval(match[1])==version,f'Version no sincronizada: {path}'
files=[root/'dist/LogiGian64-Setup.exe',root/f'dist/LogiGian64-{version}-Windows-x64.zip',
       root/f'dist/LogiGian64-{version}-source.zip',root/f'linux/dist/LogiGian64-{version}-amd64.deb',
       root/f'linux/dist/LogiGian64-{version}-Linux-source.tar.gz']
missing=[str(p) for p in files if not p.is_file()]
if missing:raise SystemExit('Falta compilar ambas plataformas:\n'+'\n'.join(missing))
from PyInstaller.utils.win32.versioninfo import read_version_info_from_executable
fixed=read_version_info_from_executable(str(files[0])).ffi
installer_version=(fixed.fileVersionMS>>16,fixed.fileVersionMS&65535,fixed.fileVersionLS>>16,fixed.fileVersionLS&65535)
assert installer_version==tuple(map(int,version.split('.')))+(0,),'Falta recompilar el instalador Windows para esta version'
manifest=json.loads((root/'dist/manifest.json').read_text())
assert manifest['version']==version,'El manifiesto Windows pertenece a otra version'
with zipfile.ZipFile(files[1]) as archive:
    assert hashlib.sha256(archive.read('LogiGian64.exe')).hexdigest()==manifest['sha256'],'El ZIP no coincide con el ejecutable Windows'
with tarfile.open(files[4]) as archive:
    data=archive.extractfile('LogiGian64-linux/nexus/__init__.py').read().decode('utf-8')
    assert f'__version__ = "{version}"' in data,'Las fuentes Linux pertenecen a otra version'
linux_manifest=json.loads((root/'linux/dist/manifest-linux.json').read_text())
assert linux_manifest['version']==version,'El manifiesto Linux pertenece a otra version'
assert linux_manifest['deb_sha256']==hashlib.file_digest(files[3].open('rb'),'sha256').hexdigest(),'El paquete Linux no coincide con su manifiesto'
folder=root/f'dist/release-{version}'
folder.mkdir(exist_ok=True)
expected={p.name for p in files}|{'manifest.json','manifest-linux.json','SHA256SUMS.txt'}
unexpected=[p.name for p in folder.iterdir() if p.name not in expected]
if unexpected:raise SystemExit('La carpeta de publicacion contiene archivos inesperados: '+', '.join(unexpected))
for path in files:shutil.copy2(path,folder/path.name)
shutil.copy2(root/'dist/manifest.json',folder/'manifest.json')
shutil.copy2(root/'linux/dist/manifest-linux.json',folder/'manifest-linux.json')
with (folder/'SHA256SUMS.txt').open('w',encoding='ascii',newline='\n') as sums:
    for path in sorted(folder.iterdir()):
        if path.name!='SHA256SUMS.txt':sums.write(hashlib.file_digest(path.open('rb'),'sha256').hexdigest()+'  '+path.name+'\n')
print(folder)
