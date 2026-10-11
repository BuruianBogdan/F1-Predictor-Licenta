import csv,io,json
from services.prediction_service import PredictionService
from services.history_service import HistoryService
from ml.training import metrics

class ExportService:
    def _csv(self,rows,columns):
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for row in rows:
            # Prevent spreadsheet formula injection in editable entity names.
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items() if k in columns})
        return buf.getvalue()
    def champion_csv(self):
        response=PredictionService().championship()
        rows=[{**p,'season':response['season'],'simulations':response['simulations'],'model_version':response['model_version'],'as_of':response['as_of']} for p in response['drivers']]
        return self._csv(rows,['season','as_of','model_version','simulations','predicted_position','driver_id','name','current_points','expected_final_points','expected_final_position','championship_probability'])
    def race_csv(self,race_id):
        response=PredictionService().predict_race(race_id)
        rows=[{**p,'race':response['race_name'],'model_version':response['model_version'],'feature_cutoff':response['feature_cutoff'],'training_cutoff':response['training_cutoff'],'mode':response['mode'],'market_enabled':response['market_factor_used'],'explanation':json.dumps(p['factors'])} for p in response['predictions']]
        return self._csv(rows,['race','feature_cutoff','training_cutoff','model_version','mode','market_enabled','predicted_position','driver_id','driver_name','constructor_name','win_probability','podium_probability','points_probability','explanation'])
    def history_csv(self):
        return self._csv(HistoryService().list_history(),['id','created_at','kind','race_id','model_version','historical_replay','valid_for_prospective_accuracy'])
    def metrics_csv(self):
        rows=[{'model':k,**v} for k,v in metrics().get('summary',{}).items()]
        return self._csv(rows,['model','races','top1_accuracy','top3_coverage','position_mae','spearman','brier_score','race_log_loss','calibration_ece'])
    def full_report_text(self):
        report=PredictionService().championship()
        return 'F1 PREDICTOR — CHAMPIONSHIP SIMULATION\nPrediction is not certainty. Probabilities are fractions.\n'+json.dumps(report,indent=2)
