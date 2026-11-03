from pathlib import Path
import zipfile,hashlib,json,sys
root=Path.cwd()
source_files=[root/name for name in ['main.py','requirements.txt','build.ps1','LogiGian64.spec','version.txt','.gitignore','package_release.py','installer.iss','RELEASE_NOTES.md','TESTING.md']]
source_files+=list((root/'nexus').glob('*.py'))+list((root/'tests').glob('*.py'))
source_files+=list((root/'assets').glob('*'))
source_files+=list((root/'.github'/'workflows').glob('*.yml'))
common=[root/name for name in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md','VALIDATION.md']]+list((root/'licenses').glob('*'))
exe=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'dist'/'LogiGian64.exe'
manifest={'name':'LogiGian64','version':'0.2.1','platform':'Windows x64','exe_bytes':exe.stat().st_size,'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'tests_passed':45,'hardware_plugins':['G502 HERO 046D:C08B volatile host buttons'],'physical_end_to_end_verified':False}
(root/'dist'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for filename in ['LogiGian64-source.zip','LogiGian64-0.2.1-source.zip']:
 with zipfile.ZipFile(root/'dist'/filename,'w',zipfile.ZIP_DEFLATED) as z:
  for file in source_files+common:z.write(file,file.relative_to(root))
for filename in ['LogiGian64-Windows-x64.zip','LogiGian64-0.2.1-Windows-x64.zip']:
 with zipfile.ZipFile(root/'dist'/filename,'w',zipfile.ZIP_DEFLATED) as z:
  z.write(exe,'LogiGian64.exe')
  z.write(root/'dist'/'manifest.json','manifest.json')
  for file in common:z.write(file,file.relative_to(root))
  for file in source_files:z.write(file,'source/'+str(file.relative_to(root)).replace('\\','/'))
print(json.dumps(manifest,indent=2))
