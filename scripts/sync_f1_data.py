import argparse,json
import _bootstrap
from database.migrations import migrate
from services.data_sync_service import F1DataSyncService

if __name__ == '__main__':
    p=argparse.ArgumentParser(description='Atomic idempotent Jolpica synchronization')
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--current',action='store_true');group.add_argument('--season',type=int);group.add_argument('--from',dest='start',type=int)
    p.add_argument('--to',dest='end',type=int)
    a=p.parse_args();migrate();svc=F1DataSyncService()
    if a.current: print(json.dumps(svc.sync_current_season(),indent=2))
    elif a.season: print(json.dumps(svc.sync_season(a.season),indent=2))
    else:
        if not a.end or a.end<a.start: p.error('--from needs --to >= start')
        for year in range(a.start,a.end+1):print(json.dumps(svc.sync_season(year)),flush=True)
