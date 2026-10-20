"""Stable Steam entry point for the currently verified development room."""
import argparse
import ctypes
import sys
from pathlib import Path
from mod import ROOT, read_json
from play_iteration_platform import play


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = read_json(ROOT/'local/grey-room-launch.json')
    if config.get('schema') != 'malemod.grey-room-launch/1':
        raise ValueError('Development room configuration needs verification')
    play(Path(config['package']), Path(config['acceptance']), check_only=args.check)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if '--check' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, str(error), 'Witcher Development Grey Room', 0x10)
        raise
