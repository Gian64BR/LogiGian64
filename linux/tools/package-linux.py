"""Run on Linux after the native PyInstaller build."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import sys

root = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from nexus import __version__ as version
dist = root/'dist'
diagnostic=subprocess.run([str(dist/'LogiGian64/LogiGian64'),'--diagnose'],text=True,capture_output=True,check=True)
assert json.loads(diagnostic.stdout)['version']==version,'Recompila el ejecutable Linux para esta version'
work = tempfile.TemporaryDirectory(prefix='logigian64-deb-')
stage = Path(work.name)  # Native filesystem: DrvFS cannot preserve Unix permissions.
app = stage/'opt/logigian64-linux'
shutil.copytree(dist/'LogiGian64', app)
shutil.copytree(root/'tools',app/'tools',ignore=shutil.ignore_patterns('bootstrap-test.sh','__pycache__'))
shutil.copy(root/'README-LINUX.md',app/'README-LINUX.md')
for script in (app/'tools').glob('*.sh'): script.chmod(0o755)
(stage/'usr/bin').mkdir(parents=True)
(stage/'usr/bin/logigian64-linux').write_text('#!/bin/sh\nexec /opt/logigian64-linux/LogiGian64 "$@"\n')
(stage/'usr/bin/logigian64-linux').chmod(0o755)
(stage/'usr/share/applications').mkdir(parents=True)
(stage/'usr/share/applications/logigian64-linux.desktop').write_text('[Desktop Entry]\nType=Application\nName=LogiGian64 Linux\nComment=Perfiles y macros para perifericos\nExec=/usr/bin/logigian64-linux\nIcon=logigian64-linux\nTerminal=false\nCategories=Utility;\nStartupWMClass=LogiGian64\n')
icons=stage/'usr/share/icons/hicolor/256x256/apps'
icons.mkdir(parents=True)
shutil.copy(root/'assets/logigian64-logo.png',icons/'logigian64-linux.png')
metadata=stage/'DEBIAN'; metadata.mkdir()
metadata.joinpath('control').write_text(f'Package: logigian64-linux\nVersion: {version}\nArchitecture: amd64\nMaintainer: LogiGian64\nSection: utils\nPriority: optional\nDepends: libc6 (>= 2.39), libudev1, libegl1, libopengl0, libxkbcommon0, libxkbcommon-x11-0, libxcb1, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-shape0, libxcb-xfixes0, libxcb-randr0, libxcb-render0, libxcb-sync1, libxcb-xkb1, libdbus-1-3, libglib2.0-0t64, libfontconfig1, libfreetype6, libgl1\nDescription: LogiGian64 Linux preview\n Perfiles, macros y control HID++ para G502 HERO. Ubuntu 24.04 / Mint 22.\n')
shutil.copy(root/'tools/prerm',metadata/'prerm'); (metadata/'prerm').chmod(0o755)
for path in stage.rglob('*'):
    if path.is_dir(): path.chmod(0o755)
    elif path.is_file(): path.chmod(0o644)
for path in (app/'LogiGian64',stage/'usr/bin/logigian64-linux',metadata/'prerm',*(app/'tools').glob('*.sh')):
    path.chmod(0o755)
deb=dist/f'LogiGian64-{version}-amd64.deb'
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(deb)],check=True)
(dist/'manifest-linux.json').write_text(json.dumps(dict(name='LogiGian64',version=version,
    platform='Linux amd64',status='preview',deb_sha256=hashlib.file_digest(deb.open('rb'),'sha256').hexdigest(),
    exe_sha256=hashlib.file_digest((dist/'LogiGian64/LogiGian64').open('rb'),'sha256').hexdigest(),
    tests_passed=89,physical_end_to_end_verified=False),indent=2),encoding='utf-8')
source=dist/f'LogiGian64-{version}-Linux-source.tar.gz'
with tarfile.open(source,'w:gz') as archive:
    def source_filter(info):
        if '__pycache__' in info.name or info.name.endswith('/bootstrap-test.sh'): return None
        info.uid=info.gid=0;info.uname=info.gname='root'
        info.mode=0o755 if info.isdir() or info.name.endswith('.sh') else 0o644
        return info
    for name in ('nexus','assets','licenses','tools','tests','main.py','requirements.txt','README-LINUX.md','RELEASE_NOTES.md','VALIDATION.md','install.sh','LICENSE','THIRD_PARTY_NOTICES.md','LogiGian64-linux.spec'):
        archive.add(root/name,arcname='LogiGian64-linux/'+name,filter=source_filter)
with (dist/'SHA256SUMS.txt').open('w') as sums:
    for path in (deb,source):
        sums.write(hashlib.file_digest(path.open('rb'),'sha256').hexdigest()+'  '+path.name+'\n')
