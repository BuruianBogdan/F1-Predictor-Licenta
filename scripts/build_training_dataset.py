import argparse
import _bootstrap
from config import DATA_DIR
from ml.feature_engineering import FeatureEngineeringService
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',default='PRE_WEEKEND',choices=['PRE_WEEKEND','POST_QUALIFYING']);a=p.parse_args()
    data=FeatureEngineeringService().dataset(a.mode);target=DATA_DIR/'datasets'/f'{a.mode.lower()}.csv';target.parent.mkdir(parents=True,exist_ok=True);data.to_csv(target,index=False)
    print(f'{len(data)} rows saved to {target}')
