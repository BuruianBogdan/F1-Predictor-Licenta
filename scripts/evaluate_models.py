import argparse,json
import _bootstrap
from ml.feature_engineering import FeatureEngineeringService
from ml.race_model import load_for_cutoff
from ml.training import evaluate
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,required=True);p.add_argument('--mode',default='PRE_WEEKEND');a=p.parse_args()
    data=FeatureEngineeringService().dataset(a.mode);data=data[data.season==a.season]
    if data.empty:p.error('No data for season')
    model,meta=load_for_cutoff(data.feature_cutoff.min(),a.mode)
    if model is None:p.error('No model trained strictly before this season')
    print(json.dumps({'model':meta,'baseline':evaluate(data),'ml':evaluate(data,model)},indent=2))
