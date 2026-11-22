"""One-time stable per-user installation; no administrator rights required."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from app_updates import APP_FILES


def stable_install_path():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PoEFateAdvisor'


def install(source:Path,target:Path):
    source=source.resolve()
    target=target.resolve()
    if source==target:
        return target
    target.mkdir(parents=True,exist_ok=True)
    for name in APP_FILES:
        p=source/name
        if p.is_file():
            shutil.copy2(p,target/name)
    for asset in (source/'assets').rglob('*'):
        if asset.is_file():
            rel=asset.relative_to(source)
            dest=target/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(asset,dest)
    # .venv, settings, secrets and learned training data are never copied.
    return target


def make_desktop_shortcut(target:Path):
    if sys.platform!='win32':return False
    # Create a .lnk without requiring pywin32.
    script='''Set sh = CreateObject("WScript.Shell")
Set link = sh.CreateShortcut(sh.SpecialFolders("Desktop") & "\\PoE Fate Advisor.lnk")
link.TargetPath = WScript.Arguments(0)
link.WorkingDirectory = WScript.Arguments(1)
link.IconLocation = "shell32.dll,3"
link.Save
'''
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',suffix='.vbs',delete=False) as f:
        f.write(script)
        temp=Path(f.name)
    try:
        result=subprocess.run(['cscript.exe','//nologo',str(temp),str(target/'PoE Fate Advisor - leiser Start.vbs'),str(target)],
                              capture_output=True,text=True,timeout=8)
        return result.returncode==0
    finally:temp.unlink(missing_ok=True)


if __name__=='__main__':
    target=install(Path(__file__).parent,stable_install_path())
    print('Installiert unter:', target)
    if make_desktop_shortcut(target):
        print('Desktop-Verknüpfung erstellt: PoE Fate Advisor')
    else:
        print('Starten über:', target/'start_windows.bat')
