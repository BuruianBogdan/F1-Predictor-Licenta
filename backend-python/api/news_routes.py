from flask import Blueprint,jsonify,request
from services.news_service import NewsService
from services.job_service import JobService
from services.circuit_service import CircuitPresentationService
news_bp=Blueprint('news',__name__)
@news_bp.get('/news')
def feed():return jsonify(articles=NewsService().feed(),status=NewsService().status())
@news_bp.get('/news/status')
def status():return jsonify(NewsService().status())
@news_bp.post('/news/refresh')
def refresh():return jsonify(JobService.submit('Selenium news + local LLM',NewsService().crawl)),202
@news_bp.post('/news/automation')
def automation():
    data=request.get_json() or {}
    return jsonify(NewsService().configure(data.get('enabled'),int(data.get('interval_minutes',30))))
@news_bp.get('/calendar')
def calendar():return jsonify(CircuitPresentationService().calendar(request.args.get('season',type=int)))

@news_bp.get('/drivers/grid')
def driver_grid():
    from database.db import SessionLocal
    from models.driver import Driver
    from models.constructor import Constructor
    from models.race import Race
    from models.analytics import RaceEntry
    from services.standings_service import StandingsService
    from services.media_service import MediaService
    from services.season_service import SeasonContext
    season=SeasonContext().get()['active_season'];standings=StandingsService().get_driver_standings(season)
    with SessionLocal() as s:
        rows=s.query(Driver,Constructor,Race).join(RaceEntry,Driver.driver_id==RaceEntry.driver_id).join(Constructor,Constructor.constructor_id==RaceEntry.constructor_id).join(Race,Race.race_id==RaceEntry.race_id).filter(Race.season_year==season).order_by(Race.date.desc()).all()
    teams={}
    for d,c,r in rows:teams.setdefault(d.driver_id,(d,c))
    out=[]
    for entry in standings:
        if entry['driver_id'] not in teams:continue
        d,c=teams[entry['driver_id']]
        out.append({**entry,**d.to_dict(),'driver_name':f'{d.forename} {d.surname}','constructor_name':c.name,**MediaService().get(d.driver_id,c.constructor_ref)})
    return jsonify(season=season,drivers=out)
