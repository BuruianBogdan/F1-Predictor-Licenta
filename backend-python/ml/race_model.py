"""Sklearn classifiers with sigmoid calibration on a later, disjoint season."""
import json
from functools import lru_cache
import numpy as np
import joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from ml.feature_engineering import FEATURES
from config import MODEL_DIR
from services.season_service import parse_time

class RaceMLModel:
    def __init__(self, algorithm='logistic'):
        self.algorithm=algorithm;self.models={};self.calibrators={};self.metadata={}
    def fit(self, fit, calibration):
        for label in ('winner','podium','points_finish'):
            if fit[label].nunique()<2 or calibration[label].nunique()<2:raise ValueError('Both classes required for temporal fitting/calibration')
            model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1500,C=0.2)) if self.algorithm=='logistic' else HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=12,l2_regularization=5,random_state=42)
            model.fit(fit[FEATURES].to_numpy(),fit[label].to_numpy())
            raw=np.clip(model.predict_proba(calibration[FEATURES].to_numpy())[:,1],1e-6,1-1e-6)
            calibrator=LogisticRegression(C=10,max_iter=1000).fit(np.log(raw/(1-raw)).reshape(-1,1),calibration[label].to_numpy())
            self.models[label]=model;self.calibrators[label]=calibrator
        return self
    def predict_matrix(self, x):
        probabilities={}
        for label,key in [('winner','win'),('podium','podium'),('points_finish','points')]:
            raw=np.clip(self.models[label].predict_proba(x)[:,1],1e-6,1-1e-6)
            probabilities[key]=self.calibrators[label].predict_proba(np.log(raw/(1-raw)).reshape(-1,1))[:,1]
        # Winner is a mutually-exclusive field distribution. Evaluate AFTER this normalization.
        probabilities['win']/=probabilities['win'].sum()
        probabilities['podium']=np.maximum(probabilities['podium'],probabilities['win'])
        probabilities['points']=np.maximum(probabilities['points'],probabilities['podium'])
        probabilities['score']=probabilities['win']
        return probabilities
    def predict(self,rows):return self.predict_matrix(np.array([[r['features'][f] for f in FEATURES] for r in rows],dtype=float))

@lru_cache(maxsize=16)
def _load(path,mtime):return joblib.load(path)

def load_for_cutoff(cutoff,mode='PRE_WEEKEND'):
    candidates=[]
    for file in MODEL_DIR.glob(f'{mode.lower()}-*.json'):
        try:
            meta=json.loads(file.read_text())
            if parse_time(meta['training_cutoff'])<parse_time(cutoff):candidates.append((meta['training_cutoff'],file,meta))
        except (ValueError,KeyError):continue
    for _,meta_file,meta in sorted(candidates,reverse=True):
        file=meta_file.with_suffix('.joblib')
        if file.exists():
            model=_load(str(file),file.stat().st_mtime_ns)
            return model,meta
    return None,{'model_version':'heuristic-baseline-v2','training_cutoff':None,'reason':'No temporally eligible trained artifact; explicit heuristic fallback'}
