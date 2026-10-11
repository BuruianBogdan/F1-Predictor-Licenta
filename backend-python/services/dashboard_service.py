import logging
from database.db import SessionLocal
from models.driver import Driver
from models.constructor import Constructor
from models.circuit import Circuit
from models.race import Race
from models.race_result import RaceResult
from services.season_service import SeasonContext
from services.standings_service import StandingsService
from services.insight_service import InsightService
from ml.training import metrics

class DashboardService:
    def get_stats(self):
        with SessionLocal() as s:return {k:s.query(m).count() for k,m in [('drivers',Driver),('constructors',Constructor),('circuits',Circuit),('races',Race),('results',RaceResult)]}
    def get_overview(self):
        from services.prediction_service import PredictionService
        from services.odds.odds_service import OddsService
        context=SeasonContext().get();latest=context['latest_completed_race'];next_race=context['next_race']
        detail=InsightService().race_detail(latest['race_id']) if latest else None
        if detail:context['latest_completed_race']=detail['race']
        if next_race:
            from services.circuit_service import CircuitPresentationService
            with SessionLocal() as s:circuit=s.get(Circuit,next_race['circuit_id'])
            context['next_race']={**next_race,'circuit':CircuitPresentationService().present(circuit)}
        preview=None;preview_error=None
        if next_race:
            try:
                preview=PredictionService().latest_forecast(next_race['race_id']);preview['predictions']=preview['predictions'][:3]
            except ValueError as exc:preview_error=str(exc)
        from services.news_service import NewsService
        return {'news':NewsService().feed(3),**context,'stats':self.get_stats(),'top_drivers':StandingsService().get_driver_standings()[:5],'top_constructors':StandingsService().get_constructor_standings()[:5],
                'winner':detail['winner'] if detail else None,'latest_podium':detail['podium'] if detail else [],'prediction_preview':preview,'prediction_error':preview_error,'model_metrics':metrics().get('summary',{}),'market':OddsService().get(next_race['race_id']) if next_race else None}
