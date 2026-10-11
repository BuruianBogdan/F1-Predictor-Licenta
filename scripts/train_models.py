import argparse,json
import _bootstrap
from ml.training import train
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--through-season',type=int);p.add_argument('--mode',default='PRE_WEEKEND',choices=['PRE_WEEKEND','POST_QUALIFYING']);a=p.parse_args()
    report=train(a.through_season,a.mode);print(json.dumps({k:v for k,v in report.items() if k not in ('folds','features')},indent=2))
