"""Build a portable Windows folder with PyInstaller. Run from the project root."""
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    if os.name!='nt':
        raise SystemExit('Build the Windows release on Windows.')
    subprocess.run([sys.executable,str(ROOT/'scripts/fetch_vendor.py')],check=True)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed',
             '--name','LagLens','--paths',str(ROOT/'src'),
             '--icon',str(ROOT/'assets/laglens.ico'),
             '--add-data',f'{ROOT/"src/laglens/ui"};laglens/ui',
             '--add-data',f'{ROOT/"vendor/PresentMon.exe"};vendor',
             '--add-data',f'{ROOT/"vendor/PresentMon-LICENSE.txt"};vendor',
             '--collect-data','webview','--hidden-import','webview.platforms.edgechromium',
             '--exclude-module','playwright','--exclude-module','pygame',
             '--exclude-module','tkinter','--exclude-module','numpy',
             str(ROOT/'run.py')]
    subprocess.run(command,cwd=ROOT,check=True)
    import shutil
    for filename in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md']:
        shutil.copy2(ROOT/filename,ROOT/'dist/LagLens'/filename)
    shutil.copytree(ROOT/'docs',ROOT/'dist/LagLens/docs',dirs_exist_ok=True)
    import importlib.metadata
    for package in ['psutil','pywebview','pythonnet','clr_loader','bottle','proxy_tools','cffi','pycparser','typing_extensions']:
        try:
            distribution=importlib.metadata.distribution(package)
            for item in distribution.files or []:
                if 'license' in item.name.lower() or item.name.lower() in ('copying','copyright'):
                    source=distribution.locate_file(item)
                    destination=ROOT/'dist/LagLens/licenses'/package/item.name
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    if source.is_file():shutil.copy2(source,destination)
        except importlib.metadata.PackageNotFoundError:
            continue
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license,ROOT/'dist/LagLens/licenses/Python-LICENSE.txt')
    print('Portable app: dist/LagLens/LagLens.exe')


if __name__=='__main__':main()
