import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import joblib
from scipy.stats import spearmanr
from sklearn.metrics import brier_score_loss, log_loss
from ml.feature_engineering import FeatureEngineeringService, FEATURES
from ml.race_model import RaceMLModel
from ml.baseline import HeuristicBaselineModel
from config import MODEL_DIR, DATA_DIR
from database.db import SessionLocal
from models.analytics import ModelMetrics
from services.season_service import utcnow, iso

def evaluate(frame,model=None):
    races=[];y=[];p=[]
    for _,race in frame.groupby('race_id',sort=False):
        rows=[{'features':row} for row in race[FEATURES].to_dict('records')]
        probabilities=(model or HeuristicBaselineModel()).predict(rows)
        win=probabilities['win'];order=np.argsort(-win,kind='stable');rank=np.argsort(order)+1
        actual=race['position'].to_numpy();winner=np.where(race['winner'].to_numpy()==1)[0]
        if len(winner)!=1:continue
        w=int(winner[0]);overlap=len(set(order[:3])&set(np.where(actual<=3)[0]))/min(3,len(race))
        races.append({'top1':int(order[0]==w),'top3':int(w in order[:3]),'podium_precision':overlap,'mae':float(np.abs(rank-actual).mean()),'spearman':float(spearmanr(rank,actual).statistic),'race_log_loss':float(-np.log(max(win[w],1e-12)))})
        y.extend(race['winner'].tolist());p.extend(win.tolist())
    if not races:raise ValueError('No evaluable races')
    bins=[];y=np.array(y);p=np.array(p)
    for low,high in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        mask=(p>=low)&(p<high if high<1 else p<=high)
        if mask.any():bins.append({'low':float(low),'high':float(high),'count':int(mask.sum()),'predicted':float(p[mask].mean()),'observed':float(y[mask].mean())})
    return {'races':len(races),'rows':len(y),'top1_accuracy':float(np.mean([r['top1'] for r in races])),'top3_coverage':float(np.mean([r['top3'] for r in races])),
            'podium_precision':float(np.mean([r['podium_precision'] for r in races])),'podium_recall':float(np.mean([r['podium_precision'] for r in races])),
            'position_mae':float(np.mean([r['mae'] for r in races])),'spearman':float(np.mean([r['spearman'] for r in races])),'brier_score':float(brier_score_loss(y,p)),
            'binary_log_loss':float(log_loss(y,p,labels=[0,1])),'race_log_loss':float(np.mean([r['race_log_loss'] for r in races])),
            'calibration_ece':float(sum(b['count']*abs(b['predicted']-b['observed']) for b in bins)/len(y)),'calibration_bins':bins}

def train(through_season=None, mode='PRE_WEEKEND'):
    through_season=through_season or utcnow().year-1
    data=FeatureEngineeringService().dataset(mode)
    if data.empty:raise ValueError('No verified data; synchronize seasons first')
    data=data[data.season<=through_season].sort_values(['date','race_id','driver_id'])
    years=sorted(data.season.unique())
    if len(years)<4:raise ValueError('At least four seasons are needed for fit/calibration/holdout')
    DATA_DIR.joinpath('datasets').mkdir(parents=True,exist_ok=True);MODEL_DIR.mkdir(parents=True,exist_ok=True)
    data.to_csv(DATA_DIR/'datasets'/f'{mode.lower()}.csv',index=False)
    folds=[]
    test_years=years[-4:]
    for year in test_years:
        past=[y for y in years if y<year]
        if len(past)<2:continue
        calibration_year=past[-1]
        fit=data[data.season<calibration_year];calibration=data[data.season==calibration_year];test=data[data.season==year]
        fold={'test_season':int(year),'fit_seasons':[int(fit.season.min()),int(fit.season.max())],'calibration_season':int(calibration_year),'baseline':evaluate(test)}
        for algorithm in ('logistic','hist_gradient_boosting'):
            model=RaceMLModel(algorithm).fit(fit,calibration)
            fold[algorithm]=evaluate(test,model)
            if algorithm=='logistic':_save(model,fit,calibration,mode)
        folds.append(fold)
    calibration_year=years[-1];fit=data[data.season<calibration_year];calibration=data[data.season==calibration_year]
    production=RaceMLModel('logistic').fit(fit,calibration);meta=_save(production,fit,calibration,mode)
    summary={}
    for name in ('baseline','logistic','hist_gradient_boosting'):
        total=sum(f[name]['races'] for f in folds)
        summary[name]={metric:sum(f[name][metric]*f[name]['races'] for f in folds)/total for metric in ('top1_accuracy','top3_coverage','podium_precision','podium_recall','position_mae','spearman','brier_score','race_log_loss','binary_log_loss','calibration_ece')}
        summary[name]['races']=total
    report={'status':'trained','model_version':meta['model_version'],'trained_at':meta['trained_at'],'training_period':meta['training_period'],'training_cutoff':meta['training_cutoff'],'feature_mode':mode,'features':FEATURES,'production_algorithm':'logistic','selection_policy':'Logistic preselected for simplicity; gradient boosting reported as a benchmark, not selected on test scores','folds':folds,'summary':summary,'market_evaluation':None,'market_note':'No archived pre-race market dataset; ML+market metrics unavailable, never fabricated','probability_unit':'fraction','limitations':['Rosters reconstructed from historical entries; future field projected','Final corrected historical results, not an as-published archive','No measured practice/weather/tyre features','Podium/points classifiers are monotonic marginals; sums need not equal 3/10','Ranking uses win probability, which may be less accurate in the midfield']}
    file=MODEL_DIR/f'metrics-{mode.lower()}.json';tmp=file.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));tmp.replace(file)
    with SessionLocal.begin() as s:s.add(ModelMetrics(model_version=meta['model_version'],created_at=meta['trained_at'],data=report))
    return report

def _save(model,fit,calibration,mode):
    end=str(calibration.date.max());cutoff=iso(datetime.fromisoformat(end).replace(tzinfo=timezone.utc)+timedelta(days=1))
    meta={'model_version':f'logistic-sigmoid-v2-{mode.lower()}-through-{int(calibration.season.max())}','trained_at':iso(utcnow()),'training_cutoff':cutoff,'training_period':[str(fit.date.min()),end],'fit_through':str(fit.date.max()),'calibration_season':int(calibration.season.max()),'feature_mode':mode,'features':FEATURES}
    model.metadata=meta
    stem=MODEL_DIR/f'{mode.lower()}-{int(calibration.season.max())}'
    temp=stem.with_suffix('.tmp');joblib.dump(model,temp);temp.replace(stem.with_suffix('.joblib'))
    temp=stem.with_suffix('.json.tmp');temp.write_text(json.dumps(meta,indent=2));temp.replace(stem.with_suffix('.json'))
    return meta

def metrics(mode='PRE_WEEKEND'):
    file=MODEL_DIR/f'metrics-{mode.lower()}.json'
    return json.loads(file.read_text()) if file.exists() else {'status':'not_trained','summary':{},'folds':[],'features':FEATURES}
