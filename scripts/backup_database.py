"""Consistent SQLite backup, safe even while the app is running."""
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def backup(source=ROOT / 'database/f1.db', directory=ROOT / 'database/backups'):
    source, directory = Path(source), Path(directory)
    if not source.exists():
        raise FileNotFoundError(source)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f'{source.stem}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.db'
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')
    return destination

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'database/f1.db')
    args = parser.parse_args()
    print(backup(args.source))
