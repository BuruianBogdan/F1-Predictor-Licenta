import argparse,json
import _bootstrap
from data_import.fastf1_importer import FastF1Importer
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('race_id',type=int);p.add_argument('--session',default='Q');p.add_argument('--telemetry',action='store_true');p.add_argument('--laps',action='store_true');a=p.parse_args()
    print(json.dumps(FastF1Importer().enrich_session(a.race_id,a.session,a.telemetry,a.laps),indent=2))
