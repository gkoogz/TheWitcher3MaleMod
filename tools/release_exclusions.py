"""Development rooms belong in Git, never anatomy installation archives."""
from pathlib import PurePosixPath


def assert_release_path(value):
    normalized = str(value).replace('\\', '/').lower()
    parts = PurePosixPath(normalized).parts
    if any(p in ('dev', 'probes', 'build', 'captures') for p in parts) or (parts and parts[0]=='local'):
        raise ValueError('Developer/private file is excluded from releases: '+str(value))
    if any(p.startswith(('modmalemoditeration', 'modmalemodcontinuetest')) for p in parts):
        raise ValueError('Sandbox content is excluded from releases: '+str(value))
    if any(p.startswith('iteration_') or p == 'autocontinue.ws' for p in parts):
        raise ValueError('Sandbox bootstrap is excluded from releases: '+str(value))
    return value
