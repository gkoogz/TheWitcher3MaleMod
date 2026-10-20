"""Scope the observed gameplay LOD settings to an unused private preview."""
import argparse
import re
from pathlib import Path
from mod import digest, write_json
from native_preview import load_preview


def prepare(path):
    path = Path(path).resolve()
    game, data = load_preview(path)
    config = game/'bin/config/base/rendering.ini'
    relative = config.relative_to(game).as_posix()
    row = next(r for r in data['files'] if r['path'] == relative)
    text = config.read_text()
    original = digest(config)
    for key in ['MeshLodGameplayDownscale', 'CharacterLodGameplayDownscale']:
        text, count = re.subn(r'(?m)^'+key+r'=0\s*$', key+'=1', text)
        if count != 1:
            raise ValueError('Expected observed stock LOD setting: '+key)
    config.write_text(text)
    row.update(sha256=digest(config), sourceSHA256=original,
               derived='Private LOD validation; both observed gameplay downscale settings set to 1')
    data['privateLODReview'] = True
    write_json(path, data)
    load_preview(path)
    return path


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('preview', type=Path)
    print(prepare(p.parse_args().preview))
