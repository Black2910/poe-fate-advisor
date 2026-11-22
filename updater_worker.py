"""Background *installer*, only launched after deliberate user confirmation.

Waits for current GUI process to exit before replacing program-only files.
Maintains installation directory, Python venv, keyring and user settings.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from app_updates import stage_package, backup_root


def wait_pid(pid:int,timeout=40):
    if sys.platform=='win32':
        import ctypes
        kernel32=ctypes.windll.kernel32
        SYNCHRONIZE=0x00100000
        proc=kernel32.OpenProcess(SYNCHRONIZE,False,pid)
        if not proc:return
        try:
            result=kernel32.WaitForSingleObject(proc,int(timeout*1000))
            if result==0x102:
                raise TimeoutError('Der alte Advisor wurde nicht geschlossen.')
        finally:kernel32.CloseHandle(proc)
    else:
        for _ in range(int(timeout*5)):
            try:os.kill(pid,0)
            except ProcessLookupError:return
            time.sleep(.2)
        raise TimeoutError('Alte App läuft noch.')


def install_from_stage(stage:Path, install_dir:Path, backup:Path):
    """File-level rollback on failure; never touch files missing from update."""
    backup.mkdir(parents=True,exist_ok=False)
    touched=[]
    try:
        for source in sorted(stage.rglob('*')):
            if not source.is_file():continue
            rel=source.relative_to(stage)
            dest=install_dir/rel
            old=dest.is_file()
            backup_file=backup/rel
            if old:
                backup_file.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(dest,backup_file)
            dest.parent.mkdir(parents=True,exist_ok=True)
            tmp=dest.with_suffix(dest.suffix+'.new_update')
            try:
                shutil.copy2(source,tmp)
                os.replace(tmp,dest)
            finally:tmp.unlink(missing_ok=True)
            touched.append((dest,backup_file,old))
    except Exception:
        for dest,saved,was_present in reversed(touched):
            if was_present and saved.exists():
                shutil.copy2(saved,dest)
            elif not was_present:
                dest.unlink(missing_ok=True)
        raise


def perform_update(package:Path, install_dir:Path):
    root=backup_root()
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    stage=root/('stage-'+stamp)
    backup=root/('backup-'+stamp)
    try:
        desc=stage_package(package,stage)
        install_from_stage(stage,install_dir,backup)
        return desc['version'],backup
    finally:
        shutil.rmtree(stage,ignore_errors=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--zip',dest='archive',required=True)
    parser.add_argument('--install',required=True)
    parser.add_argument('--python',dest='python_exe',required=True)
    args=parser.parse_args()
    log=backup_root()/'update.log'
    try:
        wait_pid(args.pid)
        version, backup=perform_update(Path(args.archive),Path(args.install))
        with log.open('a',encoding='utf-8') as out:
            out.write(f'{datetime.now().isoformat()} Update auf {version}; Backup: {backup}\n')
        subprocess.Popen([args.python_exe,str(Path(args.install)/'app.py')],
                         cwd=args.install,close_fds=True)
    except Exception as err:
        with log.open('a',encoding='utf-8') as out:
            out.write(f'{datetime.now().isoformat()} UPDATE-FEHLER: {err!r}\n')
        raise


if __name__=='__main__':main()
