from pathlib import Path
import zipfile,hashlib,json,sys
from nexus import __version__ as version
root=Path(__file__).resolve().parent
source_files=[root/name for name in ['VERSION','main.py','requirements.txt','build.ps1','LogiGian64.spec','version.txt','.gitignore','package_release.py','installer.iss','RELEASE_NOTES.md','TESTING.md','PERFORMANCE.md']]
source_files+=list((root/'nexus').glob('*.py'))+list((root/'tests').glob('*.py'))
source_files.append(root/'stop-logigian64.ps1')
source_files+=list((root/'assets').glob('*'))
source_files+=list((root/'tools').glob('*.py'))+[root/'AGENTS.md',root/'RELEASING.md']
common=[root/name for name in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md','VALIDATION.md']]+list((root/'licenses').glob('*'))
exe=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'dist'/'LogiGian64.exe'
from PyInstaller.utils.win32.versioninfo import read_version_info_from_executable
fixed=read_version_info_from_executable(str(exe)).ffi
binary_version=(fixed.fileVersionMS>>16,fixed.fileVersionMS&65535,fixed.fileVersionLS>>16,fixed.fileVersionLS&65535)
assert binary_version==tuple(map(int,version.split('.')))+(0,),'Recompila el ejecutable Windows para esta version'
manifest={'name':'LogiGian64','version':version,'platform':'Windows x64','exe_bytes':exe.stat().st_size,'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'tests_passed':158,'hardware_plugins':['G502 HERO 046D:C08B volatile host buttons'],'physical_end_to_end_verified':False}
(root/'dist'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for filename in ['LogiGian64-source.zip',f'LogiGian64-{version}-source.zip']:
 with zipfile.ZipFile(root/'dist'/filename,'w',zipfile.ZIP_DEFLATED) as z:
  for file in source_files+common:z.write(file,file.relative_to(root))
for filename in ['LogiGian64-Windows-x64.zip',f'LogiGian64-{version}-Windows-x64.zip']:
 with zipfile.ZipFile(root/'dist'/filename,'w',zipfile.ZIP_DEFLATED) as z:
  z.write(exe,'LogiGian64.exe')
  z.write(root/'dist'/'manifest.json','manifest.json')
  for file in common:z.write(file,file.relative_to(root))
  for file in source_files:z.write(file,'source/'+str(file.relative_to(root)).replace('\\','/'))
print(json.dumps(manifest,indent=2))
