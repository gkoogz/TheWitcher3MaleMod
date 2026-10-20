"""Register the verified room as a non-Steam game; requires Steam to be closed.

Uses ValvePython/vdf's binary codec. Preserves existing shortcuts and records
the exact previous file for rollback. No Steam account or game settings change.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zlib
import vdf
from mod import ROOT, digest


def register(steam, user):
    if not user.isdecimal():
        raise ValueError('Expected a numeric Steam user directory')
    active = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command',
        'Get-Process steam -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if active.stdout.strip():
        raise ValueError('Steam must finish exiting before its shortcut database is edited')
    target = steam/'userdata'/user/'config/shortcuts.vdf'
    original = target.read_bytes() if target.exists() else None
    data = vdf.binary_loads(original) if original else {'shortcuts': {}}
    entries = data['shortcuts']
    name = 'The Witcher 3 - Development Grey Room'
    executable = '"'+str(Path(sys.executable).with_name('pythonw.exe'))+'"'
    script = ROOT/'tools/play_grey_room.py'
    if not script.is_file() or not Path(executable.strip('"')).is_file():
        raise ValueError('Room launcher or windowless Python is missing')
    matches = [key for key, value in entries.items() if value.get('AppName') == name]
    if len(matches)>1:
        raise ValueError('Duplicate grey-room shortcuts require review')
    key = matches[0] if matches else str(max([int(k) for k in entries]+[-1])+1)
    appid = zlib.crc32((executable+name).encode()) | 0x80000000
    entries[key] = dict(appid=appid-(1<<32), AppName=name, Exe=executable,
        StartDir='"'+str(ROOT)+'"', icon='', ShortcutPath='',
        LaunchOptions='"'+str(script)+'"', IsHidden=0, AllowDesktopConfig=0,
        AllowOverlay=1, OpenVR=0, Devkit=0, DevkitGameID='', LastPlayTime=0,
        tags={'0':'Development'})
    # Round-trip before touching the user's file.
    encoded = vdf.binary_dumps(data)
    if vdf.binary_loads(encoded) != data:
        raise ValueError('Steam shortcut codec round trip failed')
    backup = ROOT/'local/steam-shortcuts-backup'/str(time.time_ns())
    backup.mkdir(parents=True)
    if original is not None:
        (backup/'shortcuts.vdf').write_bytes(original)
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_name('shortcuts.malemod-pending.vdf')
    if pending.exists():
        raise ValueError('Preserve an existing pending shortcut update')
    pending.write_bytes(encoded)
    pending.replace(target)
    if target.read_bytes() != encoded:
        raise RuntimeError('Steam shortcut verification failed')
    report = dict(path=str(target), sha256=digest(target), backup=str(backup),
                  appid=appid, name=name, launcher=str(script), existingShortcutsPreserved=True)
    (backup/'receipt.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steam', type=Path, required=True)
    parser.add_argument('--user', required=True)
    args=parser.parse_args()
    register(args.steam.resolve(), args.user)
