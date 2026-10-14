"""Read-only, provisional championship projection at an explicit timing cutoff."""
import math
import unicodedata
from collections import defaultdict,Counter
from database.db import SessionLocal
from models.race import Race
from models.driver import Driver
from models.constructor import Constructor
from models.race_result import RaceResult
from models.analytics import RaceEntry,SprintResult,QualifyingResult
from data_sources.timing_contract import utc_stamp,utc_iso

FIA_2026='https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_a_general_provisions_-_iss_03_-_2026-06-25.pdf'
GP=[25,18,15,12,10,8,6,4,2,1]
SHORT=[[6,4,3,2,1],[13,10,8,6,5,4,3,2,1],[19,14,12,10,8,6,4,3,2,1],GP]


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value or '').casefold() if c.isalnum())


def points_table(year,sprint=False,completion=None,green_laps=None):
    if sprint:
        table=[3,2,1] if year==2021 else [8,7,6,5,4,3,2,1]
    else:table=GP
    if completion is None:return table
    if green_laps is None:return None
    if green_laps<2:return []
    if sprint:return table if completion>=.5 else []
    if year>=2022:return SHORT[0 if completion<.25 else 1 if completion<.5 else 2 if completion<.75 else 3]
    # Older interrupted-race scoring differs. Require historical official points
    # instead of applying today's regulation to a 2021 or earlier stoppage.
    return None


class RaceControlProjectionService:
    def project(self,race_id,frame,scoring='FULL_DISTANCE'):
        if scoring not in ('FULL_DISTANCE','STOPPED_NOW'):raise ValueError('Unknown projection scoring mode')
        if not frame.get('racing'):
            return {'status':'NOT_A_RACE','label':'Championship projection','note':'Practice and qualifying do not award championship points.'}
        at=frame['at'];meta=frame['meta'];sprint=meta.get('session_name')=='Sprint'
        if not frame.get('rows') or not any(r.get('position') for r in frame['rows']):
            return {'status':'INSUFFICIENT_TIMING','note':'Waiting for an observed classification.'}
        rows=frame['rows'];leader=next((r for r in rows if r.get('position')==1),None)
        raw_total=frame.get('scheduled_laps');total=int(raw_total) if str(raw_total).isdigit() else None
        completed=leader.get('completed_laps',leader.get('lap')) if leader else None
        green_laps=None
        if scoring=='STOPPED_NOW':
            # Full lap intervals must be observed, and explicit green flags must
            # cover two consecutive leader laps. Missing history is not green.
            history=frame.get('laps_for_projection',{}).get(str(leader['driver_number']),[]) if leader else []
            consecutive=0;previous_lap=None
            for lap in history:
                current_lap=lap.get('lap')
                if previous_lap is not None and current_lap!=previous_lap+1:consecutive=0
                consecutive=consecutive+1 if lap.get('track_flag') in ('1','GREEN') and lap.get('complete') else 0
                previous_lap=current_lap
                if consecutive>=2:green_laps=2;break
        completion=completed/total if total and completed is not None else None
        with SessionLocal() as db:
            race=db.get(Race,race_id)
            if race is None:raise ValueError('Unknown race')
            year=race.season_year
            table=points_table(year,sprint,completion if scoring=='STOPPED_NOW' else None,green_laps)
            unavailable=scoring=='STOPPED_NOW' and (completion is None or table is None)
            table=[] if unavailable else table
            prior=db.query(Race).filter(Race.season_year==year,Race.round<race.round,Race.results_verified==1).all()
            ids=[r.race_id for r in prior]
            gp_results=db.query(RaceResult).filter(RaceResult.race_id.in_(ids)).all()
            sprint_results=db.query(SprintResult).join(Race,Race.race_id==SprintResult.race_id).filter(Race.season_year==year,Race.round<=race.round).all()
            # A sprint from this weekend belongs in GP base points exactly once.
            sprint_results=[r for r in sprint_results if (r.race_id!=race_id or not sprint) and utc_stamp(r.available_at) is not None and utc_stamp(r.available_at)<=at]
            entrants=db.query(RaceEntry).filter_by(race_id=race_id).all()
            drivers={d.driver_id:d for d in db.query(Driver).all()};teams={c.constructor_id:c for c in db.query(Constructor).all()}
            dpoints=defaultdict(float);cpoints=defaultdict(float);dfinishes=defaultdict(Counter);cfinishes=defaultdict(Counter)
            for result in gp_results+sprint_results:
                dpoints[result.driver_id]+=result.points or 0;cpoints[result.constructor_id]+=result.points or 0
                if isinstance(result,RaceResult) and result.position:
                    dfinishes[result.driver_id][result.position]+=1;cfinishes[result.constructor_id][result.position]+=1
            dquals=defaultdict(Counter);cquals=defaultdict(Counter)
            priorquals=db.query(QualifyingResult).filter(QualifyingResult.race_id.in_(ids+[race_id])).all()
            priorquals=[q for q in priorquals if utc_stamp(q.available_at) is not None and utc_stamp(q.available_at)<=at]
            entry_teams={(e.race_id,e.driver_id):e.constructor_id for e in db.query(RaceEntry).filter(RaceEntry.race_id.in_(ids+[race_id])).all()}
            for q in priorquals:
                if q.position:
                    dquals[q.driver_id][q.position]+=1
                    if (q.race_id,q.driver_id) in entry_teams:cquals[entry_teams[q.race_id,q.driver_id]][q.position]+=1
            mapping={};unmatched=[]
            for row in rows:
                candidates=[e for e in entrants if normalized((drivers[e.driver_id].forename or '')+' '+(drivers[e.driver_id].surname or ''))==normalized(row.get('name'))]
                if not candidates:
                    candidates=[e for e in entrants if drivers[e.driver_id].code==row.get('code')]
                if len(candidates)==1:mapping[row['driver_number']]=candidates[0]
                else:unmatched.append(row.get('code') or row['driver_number'])
            def rank(points,finishes,quals):
                return sorted(points,key=lambda i:(-points[i],*[-finishes[i][p] for p in range(1,31)],*([-quals[i][p] for p in range(1,31)] if year>=2026 else []),i))
            for e in entrants:dpoints[e.driver_id]+=0;cpoints[e.constructor_id]+=0
            dbefore={i:p for p,i in enumerate(rank(dpoints,dfinishes,dquals),1)};cbefore={i:p for p,i in enumerate(rank(cpoints,cfinishes,cquals),1)}
            baseline_source='Verified GP results before round '+str(race.round)+' plus published Sprint results available at cutoff'
            increment_d=defaultdict(float);increment_c=defaultdict(float);eligibility={}
            for row in rows:
                entry=mapping.get(row['driver_number'])
                if not entry:continue
                position=row.get('position');status=row.get('status') or ('DNF' if row.get('condition',{}).get('retired') else None);eligible=status not in ('DSQ','DNS')
                if status=='DNF':
                    laps=row.get('completed_laps',row.get('lap'))
                    eligible=completed is not None and completed>0 and laps is not None and laps>=math.floor(completed*.9)
                eligibility[entry.driver_id]=eligible
                if eligible and position and not unavailable:
                    increment_d[entry.driver_id]=table[position-1] if 0<position<=len(table) else 0
            # A published dead heat shares the points for occupied finishing slots.
            ties=defaultdict(list)
            for row in rows:
                entry=mapping.get(row['driver_number'])
                if entry and row.get('position') and eligibility.get(entry.driver_id):ties[row['position']].append(entry)
            for position,entries in ties.items():
                if len(entries)>1:
                    shared=sum(table[position-1:position-1+len(entries)])/len(entries) if table else 0
                    for e in entries:increment_d[e.driver_id]=shared
            fastest_bonus=None
            if not sprint and 2019<=year<=2024 and not unavailable and (scoring=='FULL_DISTANCE' or completion>=.5):
                valid=[r for r in rows if r.get('best_lap') is not None and r.get('position') and r.get('position')<=10 and r.get('status') not in ('DSQ','DNS')]
                if valid:
                    best=min(r['best_lap'] for r in valid)
                    # All drivers' bests must be known to establish the fastest lap.
                    all_valid=[r for r in rows if r.get('status') not in ('DSQ','DNS')]
                    if all(r.get('best_lap') is not None for r in all_valid):
                        absolute=min(r['best_lap'] for r in all_valid)
                        winners=[r for r in valid if r['best_lap']==absolute]
                        for row in winners:
                            entry=mapping.get(row['driver_number'])
                            if entry:increment_d[entry.driver_id]+=1/len(winners)
                        fastest_bonus=[r['code'] for r in winners]
            for row in rows:
                entry=mapping.get(row['driver_number'])
                if entry:
                    increment_c[entry.constructor_id]+=increment_d[entry.driver_id]
                    if not sprint and eligibility.get(entry.driver_id) and row.get('position'):
                        dfinishes[entry.driver_id][row['position']]+=1;cfinishes[entry.constructor_id][row['position']]+=1
            # Entries with no earlier points have a verified zero season total.
            for e in entrants:dpoints[e.driver_id]+=0;cpoints[e.constructor_id]+=0
            dtotal={i:p+increment_d[i] for i,p in dpoints.items()};ctotal={i:p+increment_c[i] for i,p in cpoints.items()}
            output_d=[];output_c=[]
            for position,i in enumerate(rank(dtotal,dfinishes,dquals),1):
                d=drivers[i];output_d.append({'driver_id':i,'code':d.code,'name':f'{d.forename} {d.surname}','position':position,'official_points':dpoints[i],'session_points':None if unavailable else increment_d[i],'projected_points':None if unavailable else dtotal[i],'position_change':dbefore[i]-position})
            for position,i in enumerate(rank(ctotal,cfinishes,cquals),1):
                output_c.append({'constructor_id':i,'name':teams[i].name,'position':position,'official_points':cpoints[i],'session_points':None if unavailable else increment_c[i],'projected_points':None if unavailable else ctotal[i],'position_change':cbefore[i]-position})
            return {'status':'UNVERIFIED_STOPPAGE_RULES' if unavailable else 'PARTIAL' if unmatched else 'PROVISIONAL',
                    'label':'Championship if race ended now','scoring_mode':scoring,'season':year,'session_key':meta['session_key'],
                    'cutoff_utc':utc_iso(at),'source':frame.get('source','OpenF1 historical observations'),'baseline_source':baseline_source,
                    'classification':'PROVISIONAL','points_table':table,'fastest_lap_bonus':fastest_bonus,'drivers':output_d,'constructors':output_c,
                    'unmatched_drivers':unmatched,'rules_url':FIA_2026 if year==2026 else None,
                    'note':('Stopped-now scoring needs scheduled laps and two observed consecutive green leader laps; no points are inferred.' if unavailable else
                            'Full-distance points applied to the current order. Final penalties and classification can change this projection.' if scoring=='FULL_DISTANCE' else
                            'Shortened-distance points applied provisionally; final penalties and classification can change this projection.'),
                    'official_standings_modified':False,'scheduled_laps':total,'completed_leader_laps':completed,
                    'green_lap_requirement_verified':green_laps is not None,'tie_break_note':'GP finish countback, then qualifying countback from 2026. A fully unresolved tie is displayed provisionally; entity ID only stabilizes presentation.'}
