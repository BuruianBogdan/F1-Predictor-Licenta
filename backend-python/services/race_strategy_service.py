"""Experimental on-track estimates, using only observations available at the frame cutoff.
Tyre wear is a set-level model index, never four measured wheel percentages.
"""
import math,re,statistics,bisect
from datetime import datetime,timezone
import numpy as np

def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def stamp(v):
    if not v:return None
    d=datetime.fromisoformat(v.replace('Z','+00:00'));return d.replace(tzinfo=timezone.utc).timestamp() if d.tzinfo is None else d.timestamp()
def clipped(v,lo,hi):return max(lo,min(hi,v))
def minimum(a,default):return min(a) if a else default

# Tunable assumptions, not Pirelli-measured lifetimes. Normalize to a 5 km lap.
LIFE={'SOFT':28.,'MEDIUM':42.,'HARD':55.,'INTERMEDIATE':32.,'WET':38.}
DEG={'SOFT':.055,'MEDIUM':.035,'HARD':.020,'INTERMEDIATE':.040,'WET':.045}
PALETTE=[(0,'#62dca1'),(35,'#ead35b'),(60,'#f79a46'),(85,'#ef5b58')]

def colour(wear):
    if wear is None:return '#596273'
    stops=[(0,(98,220,161)),(35,(234,211,91)),(60,(247,154,70)),(85,(239,91,88)),(100,(239,91,88))]
    for (a,c1),(b,c2) in zip(stops,stops[1:]):
        if wear<=b:
            k=clipped((wear-a)/(b-a),0,1);return '#'+''.join(f'{round(x+(y-x)*k):02x}' for x,y in zip(c1,c2))
    return '#ef5b58'

class RaceStrategyService:
    version='on-track-strategy-v1'

    @staticmethod
    def incident_state(controls,number):
        impact=None;components={part:'UNKNOWN' for part in ('front_wing','rear_wing','body','floor')};confirmed_retirement=False
        for r in controls:
            text=(r.get('message') or '').upper()
            numbers={int(n) for n in re.findall(r'\b(\d{1,3})\s*\([A-Z]{3}\)',text)}
            numbers.update(int(n) for n in re.findall(r'\bCAR\s+(\d{1,3})\b',text))
            if r.get('driver_number') is not None:numbers.add(int(r['driver_number']))
            if number not in numbers:continue
            if re.search(r'\bRETIRED\b|\bRETIREMENT CONFIRMED\b',text):confirmed_retirement=True
            # A penalty / track-limit investigation alone is not evidence of damage.
            collision=bool(re.search(r'\bCOLLISION\b|\bCRASH(?:ED)?\b|\bCONTACT\b|\bACCIDENT\b',text)) and 'NO COLLISION' not in text
            damage=bool(re.search(r'\bDAMAGE(?:D)?\b|\bBROKEN\b',text))
            stopped='STOPPED ON TRACK' in text
            if collision or damage or stopped:
                impact={'kind':'DAMAGE_REPORTED' if damage else 'COLLISION_REPORTED' if collision else 'STOPPED_ON_TRACK','message':r.get('message'),'reported_at':r.get('date'),'source':'Race Control','damage_extent_known':False}
            for part,words in [('front_wing','FRONT WING'),('rear_wing','REAR WING'),('floor','FLOOR'),('body','BODYWORK')]:
                if words in text and damage:components[part]='DAMAGE_REPORTED'
                if words in text and re.search(r'\bREPLACED\b|\bREPAIRED\b',text):components[part]='REPAIR_REPORTED'
        return {'report':impact,'components':components,'retired':confirmed_retirement,'body_alert':bool(impact and impact['kind'] in ('COLLISION_REPORTED','DAMAGE_REPORTED')),'note':'Impact alert from an official message; unreported physical damage remains unknown.'}

    def build_flags(self,controls):
        self.flag_times=[];self.flag_values=[];global_flag='UNKNOWN';sectors={};safety=None
        for r in controls:
            t=stamp(r.get('date'))
            if t is None:continue
            text=(r.get('message') or '').upper();flag=r.get('flag')
            if r.get('scope')=='Sector':
                if flag in ('CLEAR','GREEN'):sectors.pop(r.get('sector'),None)
                elif flag:sectors[r.get('sector')]=flag
            elif r.get('scope')=='Track' and flag:global_flag=flag
            if r.get('category')=='SafetyCar':
                if 'DEPLOYED' in text:safety='VSC' if 'VIRTUAL' in text else 'SC'
                if 'ENDED' in text or 'IN PIT LANE' in text:safety=None
            value=safety or ('YELLOW' if sectors else global_flag)
            if not self.flag_values or self.flag_values[-1]!=value:self.flag_times.append(t);self.flag_values.append(value)

    def _flag_at(self,controls,at):
        if not hasattr(self,'flag_times'):self.build_flags(controls)
        index=bisect.bisect_right(self.flag_times,at)-1
        return self.flag_values[index] if index>=0 else 'UNKNOWN'

    def clean_laps(self,frame,row):
        history=frame.get('_laps_by',{}).get(row['driver_number'],[]) or frame.get('_laps_by',{}).get(str(row['driver_number']),[])
        pits=frame.get('_pits_by',{}).get(row['driver_number'],[]);controls=frame.get('_controls',[]);result=[]
        for lap in history:
            if not lap.get('complete') or lap.get('deleted') or lap.get('pit_out') or not finite(lap.get('time')):continue
            began=stamp(lap.get('date_start'));finished=stamp(lap.get('date_end')) or (began+lap['time'] if began is not None else None)
            if finished is not None and finished>frame['at']:continue
            if began is not None:
                if any(began<=stamp(p['date'])<=finished for p in pits if p.get('date')):continue
                flags=[self._flag_at(controls,began),self._flag_at(controls,finished)]
                flags += self.flag_values[bisect.bisect_right(self.flag_times,began):bisect.bisect_left(self.flag_times,finished)]
                if any(f not in ('GREEN','CLEAR','UNKNOWN','CHEQUERED') for f in flags):continue
            elif lap.get('track_flag') not in (None,'1','GREEN'):continue
            result.append(lap)
        if not result:return []
        fastest=min(l['time'] for l in result)
        # Exclude markedly slow laps; fuel and traffic still make this a heuristic.
        result=[l for l in result if l['time']<=fastest*1.065]
        return sorted(result,key=lambda l:l['lap'])

    def tyre_estimate(self,frame,row,length):
        age=row.get('tyre_age');compound=row.get('compound');laps=self.clean_laps(frame,row)
        stint_start=row.get('stint_start_lap')
        stint=[l for l in laps if stint_start is None or l['lap']>=stint_start][-8:]
        slopes=[(b['time']-a['time'])/(b['lap']-a['lap']) for i,a in enumerate(stint) for b in stint[i+1:] if b['lap']>a['lap']]
        observed=statistics.median(slopes) if len(stint)>=4 and slopes else None
        degradation=clipped(observed,0,.15) if observed is not None else DEG.get(compound,.035)
        heat=frame.get('weather',{}).get('track_temperature') if frame.get('weather') else None
        temp_factor=clipped(1+((heat-35)*.004 if finite(heat) else 0),.9,1.15)
        trend_factor=clipped(1+max(0,degradation-DEG.get(compound,.035))*2.5,1,1.25)
        life=LIFE.get(compound);effective=life*5/max(3,length)/temp_factor/trend_factor if life else None
        wear=round(clipped(100*(max(0,age)/effective)**1.08,0,100),1) if finite(age) and effective else None
        pace=statistics.median(l['time'] for l in stint[-5:]) if stint else statistics.median(l['time'] for l in laps[-5:]) if laps else None
        recent=stint[-5:] or laps[-5:]
        if recent:
            baselines=[]
            for lap in recent:
                sample_age=lap.get('tyre_age_laps')
                if not finite(sample_age):sample_age=max(0,lap['lap']-(stint_start or 1)+(row.get('tyre_age_at_start') or 0)) if stint else age
                sample_deg=DEG.get(lap.get('compound'),degradation) if lap.get('compound') and lap['compound']!=compound else degradation
                baselines.append(lap['time']-sample_deg*sample_age if finite(sample_age) else lap['time'])
            base=statistics.median(baselines)
        else:base=None
        return {'wear_percent':wear,'remaining_percent':round(100-wear,1) if wear is not None else None,'color':colour(wear),'compound':compound,'age_laps':age,'estimated_life_laps':round(effective,1) if effective else None,'degradation_s_per_lap':round(degradation,4),'degradation_source':'observed stint trend' if observed is not None else 'compound assumption','clean_laps_used':len(stint),'base_pace_s':base,'recent_pace_s':pace,'method':'set_wear_index','confidence':'low; fuel, traffic and underlying compound are not measured','per_wheel_measured':False,'wheels':{k:wear for k in ('FL','FR','RL','RR')},'note':'One estimate for the tyre set. Four independent wheel-wear sensors are not publicly available.'}

    @staticmethod
    def pit_multiplier(flag):
        if 'VSC' in flag:return .65
        if 'SAFETY CAR' in flag or flag=='SC':return .50
        if 'YELLOW' in flag:return .90 # Local yellow is not a full neutralisation.
        return 1.

    def green_pit_loss(self,frame):
        losses=[]
        for row in frame['rows']:
            laps=self.clean_laps(frame,row)
            if not laps:continue
            baseline=statistics.median(l['time'] for l in laps[-5:])
            for pit in frame.get('_pits_by',{}).get(row['driver_number'],[]):
                t=stamp(pit.get('date'));lane=pit.get('lane_duration') or pit.get('pit_duration')
                if t is None or not finite(lane) or t+lane>frame['at'] or self._flag_at(frame.get('_controls',[]),t) not in ('GREEN','CLEAR','UNKNOWN'):continue
                history=frame.get('_laps_by',{}).get(row['driver_number'],[])
                lap=next((l for l in history if l.get('date_start') and stamp(l['date_start'])<=t<=stamp(l['date_start'])+(l.get('time') or 0) and l.get('complete')),None)
                if lap and finite(lap.get('time')):
                    loss=lap['time']-baseline
                    if 8<=loss<=45:losses.append(loss)
        return (statistics.median(losses),'observed completed green-flag pit laps') if len(losses)>=3 else (24.,'assumed 24 s green-flag net loss; insufficient clean stops')

    def forecast(self,frame,data,length):
        if not frame['racing']:return {'status':'NOT_A_RACE','note':'Winner strategy estimates run in a Grand Prix or Sprint. Practice / qualifying keep timing and tyre estimates.'}
        active=[r for r in frame['rows'] if r.get('status') not in ('DNF','DNS','DSQ') and not r['condition']['retired'] and r.get('position')]
        if frame.get('winner') and frame['phase']=='FINISHED':
            winner=frame['winner']['driver_number'];return {'status':'FINAL_RESULT','model_version':self.version,'feature_cutoff':frame['at'],'predictions':[{'driver_number':r['driver_number'],'code':r['code'],'name':r['name'],'color':r['color'],'win_probability':1. if r['driver_number']==winner else 0.,'expected_position':float(r['position'] or 99)} for r in frame['rows']],'note':'Confirmed classification, not a prediction.'}
        if len(active)<2 or not max((r.get('lap',0) for r in active),default=0):return {'status':'INSUFFICIENT_TIMING','note':'Waiting for race laps and gaps. Unknown gaps are not replaced with invented distances.'}
        public_total=data.get('public_state',{}).get('LapCount',{}).get('TotalLaps')
        total=int(public_total) if str(public_total).isdigit() else math.ceil((100 if data['meta'].get('session_name')=='Sprint' else 260 if data['meta'].get('circuit_short_name')=='Monte Carlo' else 305)/max(3,length))
        total_source='public LapCount' if str(public_total).isdigit() else 'nominal race distance / circuit length assumption'
        for message in frame.get('_controls',[]):
            match=re.search(r'(?:RACE (?:WILL BE|DISTANCE IS)|TOTAL)\s+(\d+)\s+LAPS',message.get('message','').upper())
            if match:total=int(match[1]);total_source='Race Control announcement'
        leader=next((r for r in active if r['position']==1),active[0]);remaining=max(1,total-int(leader.get('lap') or 1)+1)
        known_paces=[r['tyre_estimate']['base_pace_s'] for r in active if finite(r['tyre_estimate']['base_pace_s'])]
        fallback=statistics.median(known_paces) if known_paces else None
        if fallback is None:return {'status':'INSUFFICIENT_TIMING','note':'Waiting for representative completed laps before estimating strategy.'}
        green_loss,loss_source=self.green_pit_loss(frame);mult=self.pit_multiplier(frame['flag']);pit_loss=green_loss*mult
        projections=[]
        known_ages=[r['tyre_age'] for r in active if finite(r.get('tyre_age'))];fallback_age=statistics.median(known_ages) if known_ages else 15.
        for row in sorted(active,key=lambda r:r['driver_number']):
            est=row['tyre_estimate'];base=est['base_pace_s'] if finite(est['base_pace_s']) else fallback
            gap=row.get('gap')
            if row['position']==1:gap=0.
            if isinstance(gap,str):
                match=re.search(r'(\d+)\s*LAPS?',gap.upper());gap=int(match[1])*fallback if match else None
            if not finite(gap):continue
            compound=row.get('compound') or 'MEDIUM';age=row.get('tyre_age') if finite(row.get('tyre_age')) else fallback_age
            life=est.get('estimated_life_laps') or LIFE.get(compound,42)*5/max(3,length)
            deg=est['degradation_s_per_lap'];cost=gap;planned=[]
            if row.get('in_pit'):
                elapsed=max(0,frame['at']-(stamp(row.get('pit_entry_at')) or frame['at']));cost+=max(0,pit_loss-elapsed);age=0
            for lap in range(remaining):
                if age>=life*.82 and remaining-lap>3:
                    stop_loss=pit_loss if lap==0 else green_loss
                    cost+=stop_loss;planned.append({'in_laps':lap,'estimated_net_loss_s':round(stop_loss,1)});age=0;compound='HARD' if remaining-lap>25 else 'MEDIUM';life=LIFE[compound]*5/max(3,length);deg=DEG[compound]
                cost+=base+deg*age+max(0,age/life-.70)**2*4;age+=1
            projections.append({'row':row,'cost':cost,'stops':planned,'pace':base+deg*(row.get('tyre_age') or 0),'sigma':4+math.sqrt(remaining)*1.4+len(planned)*3+(8 if est['recent_pace_s'] is None else 0)+(8 if not finite(row.get('tyre_age')) else 0)})
        if len(projections)<max(2,math.ceil(.5*len(active))):return {'status':'INSUFFICIENT_TIMING','note':'Too many gaps are missing for a useful race estimate.'}
        rng=np.random.default_rng(42);draws=1800
        costs=np.array([p['cost'] for p in projections]);sigma=np.array([p['sigma'] for p in projections])
        finish=costs+rng.normal(size=(draws,len(projections)))*sigma;order=np.argsort(finish,axis=1);wins=np.bincount(order[:,0],minlength=len(projections))/draws
        ranks=np.argsort(order,axis=1).mean(axis=0)+1;predictions=[]
        for i,p in enumerate(projections):
            r=p['row'];predictions.append({'driver_number':r['driver_number'],'code':r['code'],'name':r['name'],'color':r['color'],'position':r['position'],'win_probability':float(wins[i]),'expected_position':round(float(ranks[i]),2),'projected_pace_s':round(p['pace'],3),'planned_stops':p['stops'],'wear_percent':r['tyre_estimate']['wear_percent']})
        predictions.sort(key=lambda r:(-r['win_probability'],r['expected_position'],r['driver_number']))
        selected=next((p for p in projections if p['row']['driver_number']==(frame.get('selected') or {}).get('driver_number')),None)
        ahead=next((p for p in projections if selected and p['row']['position']==selected['row']['position']-1),None)
        battle=None
        if selected and ahead:
            relative=(selected['row'].get('gap') or 0)-(ahead['row'].get('gap') or 0) if finite(selected['row'].get('gap')) and finite(ahead['row'].get('gap')) else None
            gain=ahead['pace']-selected['pace']
            battle={'ahead_code':ahead['row']['code'],'gap_s':round(relative,3) if relative is not None else None,'estimated_gain_s_per_lap':round(gain,3),'catch_laps':round(relative/gain,1) if relative is not None and relative>0 and gain>.05 else None,'note':'Pace comparison only; traffic, defence and pit timing can change the outcome.'}
        return {'status':'ESTIMATE','model_version':self.version,'experimental':True,'feature_cutoff':frame['at'],'simulations':draws,'remaining_laps':remaining,'total_laps':total,'total_laps_source':total_source,'green_pit_loss_s':round(green_loss,1),'current_pit_loss_s':round(pit_loss,1),'pit_loss_source':loss_source,'neutralisation_factor':mult,'predictions':predictions,'coverage':{'drivers_modelled':len(projections),'active_drivers':len(active),'observed_tyre_ages':len(known_ages)},'battle':battle,'note':'Experimental forecast from current gaps, observed clean pace, tyre age and estimated future stops. Not a calibrated win-probability model.','assumptions':['Tyre wear is a set-level model index, not a sensor reading.','Local yellow assumes only 10% pit-loss reduction; SC / VSC use separate factors.','Future stops, fuel, traffic, new accidents and restart timing are uncertain.','Missing tyre age uses the field median (15 laps when none are known), with wider uncertainty; it is not treated as a fresh set.','No future laps, final results or future actual pit durations enter the estimate.']}

    def enrich(self,frame,data,length=5.):
        controls=[r for r in frame.get('_controls',[]) if r.get('date') and stamp(r['date'])<=frame['at']];frame['_controls']=controls;self.build_flags(controls)
        for row in frame['rows']:
            row['condition']=self.incident_state(controls,row['driver_number']);row['tyre_estimate']=self.tyre_estimate(frame,row,length)
        frame['selected']=next((r for r in frame['rows'] if frame.get('selected') and r['driver_number']==frame['selected']['driver_number']),None)
        frame['incidents']=[{**r['condition']['report'],'driver_number':r['driver_number'],'code':r['code'],'name':r['name']} for r in frame['rows'] if r['condition']['report']]
        frame['incidents'].sort(key=lambda r:r.get('reported_at') or '',reverse=True)
        frame['race_forecast']=self.forecast(frame,data,length)
        for key in ('_laps_by','_controls','_pits_by'):frame.pop(key,None)
        return frame
