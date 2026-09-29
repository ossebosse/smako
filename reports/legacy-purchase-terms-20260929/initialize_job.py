"""Closed private clone under both existing operation locks; no activation."""
import shutil
import sqlite3
from pathlib import Path
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path

P=Path('/work');S=Path('/prior')
assert not (P/'grocery.sqlite').exists()
lock=production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes',allow_missing_database=True)
with RefreshRunLock(S/'price-universes/.refresh-locks'/lock.name),RefreshRunLock(lock):
    for f in S.iterdir():
        if f.name.endswith(('-wal','-shm')):continue
        if f.is_dir():
            shutil.copytree(f,P/f.name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.refresh-locks'))
        elif f.suffix=='.sqlite':
            with sqlite3.connect(f'file:{f}?mode=ro',uri=True) as src,sqlite3.connect(P/f.name) as dest:src.backup(dest)
        else:shutil.copyfile(f,P/f.name)
print('Closed private clone of verified municipality candidate complete')
