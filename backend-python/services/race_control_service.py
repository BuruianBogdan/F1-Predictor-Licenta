"""Real timing timeline. Replay and live share the same timestamp-filtered rendering."""
import bisect,copy,gzip,json,math,re,threading,time,os,atexit
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from config import DATA_DIR
from database.db import SessionLocal
from models.race import Race
from models.circuit import Circuit
from models.driver import Driver
from services.season_service import utcnow,parse_time,iso,SeasonContext
from services.circuit_service import CircuitPresentationService
from services.media_service import MediaService
from data_sources.race_control_provider import RaceControlProvider
from services.race_strategy_service import RaceStrategyService
from services.track_geometry_service import add_track_landmarks,measured_pit_state
from data_sources.public_timing_provider import PublicTimingFeed,merge_patch,indexed,seconds
from data_sources.timing_contract import FeedHealth,TimingSettings,PatchLedger,decode_channel,numeric,utc_stamp,utc_iso
from services.race_control_checkpoint import TimingCheckpointStore
from services.race_control_projection_service import RaceControlProjectionService
from services.race_control_results import confirm_result
from data_sources.race_control_sources import FastF1RaceControlArchive

CODES={'Practice 1':'FP1','Practice 2':'FP2','Practice 3':'FP3','Sprint Qualifying':'SQ','Sprint Shootout':'SQ','Sprint':'SPRINT','Qualifying':'Q','Race':'R'}

def stamp(value):
    try:return parse_time(value).timestamp() if value else None
    except (ValueError,TypeError,OverflowError):return None

def finite(value):return isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value)

def sorted_rows(rows):return sorted(rows,key=lambda row:stamp(row.get('date')) or 0)

def last_at(rows,at):
    # Lists of small events; location/car channels use compact arrays and binary search.
    return next((row for row in reversed(rows) if (stamp(row.get('date')) or float('inf'))<=at),None)

def series_window(series,start,end):
    lo=bisect.bisect_left(series,start,key=lambda p:p[0]);hi=bisect.bisect_right(series,end,key=lambda p:p[0])
    return series[max(0,lo-1):min(len(series),hi+1)]

def make_track(data):
    candidates=sorted((lap for lap in data['events'].get('laps',[]) if finite(lap.get('lap_duration')) and lap.get('date_start') and not lap.get('is_pit_out_lap')),key=lambda r:r['lap_duration'])
    for lap in candidates:
        start=stamp(lap['date_start']);end=start+lap['lap_duration']
        points=[p for p in series_window(data['locations'].get(str(lap['driver_number']),[]),start,end) if start<=p[0]<=end and (p[1] or p[2])]
        if len(points)<50:continue
        xs=[p[1] for p in points];ys=[p[2] for p in points]
        if max(xs)-min(xs)<100 or max(ys)-min(ys)<100:continue
        return {'points':[[p[1],p[2]] for p in points],'bounds':[min(xs),min(ys),max(xs),max(ys)],'source':data.get('source','OpenF1')+' measured lap trajectory','driver_number':lap['driver_number'],'lap':lap['lap_number']}
    return None

def track_sectors(data):
    track=data.get('track')
    if not track or 'sectors' in track:return
    lap=next((l for l in data['events'].get('laps',[]) if l['driver_number']==track['driver_number'] and l['lap_number']==track['lap']),None)
    if not lap or not lap.get('date_start'):return
    points=data['locations'].get(str(track['driver_number']),[]);at=stamp(lap['date_start']);sectors=[]
    for sector in (1,2):
        value=lap.get(f'duration_sector_{sector}')
        if not finite(value):break
        at+=value;near=series_window(points,at-.7,at+.7)
        if near:
            p=min(near,key=lambda point:abs(point[0]-at));sectors.append({'sector':sector,'x':p[1],'y':p[2]})
    track['sectors']=sectors

def time_extent(data):
    """Use actual SessionStatus times; a delayed/red-flagged race can exceed its schedule."""
    meta=data['meta'];controls=data['events'].get('race_control',[])
    starts=[stamp(r.get('date')) for r in controls if 'SESSION STARTED' in (r.get('message') or '').upper() and r.get('date')]
    finishes=[stamp(r.get('date')) for r in controls if any(word in (r.get('message') or '').upper() for word in ('SESSION FINISHED','SESSION ENDED')) and r.get('date')]
    actual_start=min(starts) if starts else stamp(meta['date_start'])
    actual_end=max([stamp(meta['date_end'])]+finishes)
    meta['timeline_start']=iso(parse_time(meta['date_start'])+timedelta(seconds=actual_start-stamp(meta['date_start'])))
    meta['terminal_finish']=max(finishes) if finishes else None
    meta['timeline_end']=iso(parse_time(meta['date_end'])+timedelta(seconds=actual_end-stamp(meta['date_end'])))
    return actual_start,actual_end

class TimingTimeline:
    """Never exposes future laps, flags, weather, tyre changes or final classification."""
    @staticmethod
    def frame(data,at,driver_number):
        meta=data['meta'];events=data['events'];start=stamp(meta.get('timeline_start') or meta['date_start']);end=stamp(meta.get('timeline_end') or meta['date_end']);at=max(start,min(at,end+600)) if data.get('complete_archive') else max(start,at)
        controls=[r for r in events.get('race_control',[]) if (stamp(r.get('date')) or float('inf'))<=at]
        global_flag='UNKNOWN';sectors={};safety=None;phase='WAITING';rain_risk=None;surface='UNKNOWN'
        deleted=set()
        final_finishes=[stamp(r['date']) for r in events.get('race_control',[]) if r.get('date') and any(s in (r.get('message') or '').upper() for s in ('SESSION FINISHED','SESSION ENDED'))]
        terminal_finish=max(final_finishes) if final_finishes else meta.get('terminal_finish')
        for r in controls:
            msg=(r.get('message') or '').upper();flag=r.get('flag');scope=r.get('scope')
            if 'SESSION STARTED' in msg:phase='RUNNING'
            if 'SESSION FINISHED' in msg or 'SESSION ENDED' in msg:phase='FINISHED' if terminal_finish is not None and at>=terminal_finish else 'BREAK'
            if 'SESSION ABORTED' in msg or flag=='RED':phase='SUSPENDED'
            if flag and scope=='Sector':
                if flag in ('CLEAR','GREEN'):sectors.pop(str(r.get('sector')),None)
                else:sectors[str(r.get('sector'))]=flag
            elif flag and scope=='Track':
                global_flag=flag
                if flag=='CHEQUERED':phase='FINISHING'
            if r.get('category')=='SafetyCar':
                if 'DEPLOYED' in msg:safety='VSC' if 'VIRTUAL' in msg else 'SAFETY CAR'
                if 'IN THIS LAP' in msg:safety=(safety or 'SAFETY CAR')+' · IN THIS LAP'
                if 'ENDING' in msg:safety='VSC · ENDING'
                if 'ENDED' in msg or 'IN PIT LANE' in msg:safety=None
            risk=re.search(r'RISK OF RAIN.*?(\d+)%',msg)
            if risk:rain_risk=int(risk[1])
            if re.search(r'\bTRACK (?:IS )?WET\b',msg):surface='WET'
            if re.search(r'\bTRACK (?:IS )?DAMP\b',msg):surface='DAMP'
            if re.search(r'\bTRACK (?:IS )?DRY\b',msg):surface='DRY'
            deletion=re.search(r'CAR (\d+).*TIME (\d+):(\d+\.\d+) (DELETED|REINSTATED).*LAP (\d+)',msg)
            if deletion:
                driver=int(deletion[1]);duration=int(deletion[2])*60+float(deletion[3])
                # Published lap numbers can differ from telemetry lap numbering; match the time too.
                matching=[lap for lap in events.get('laps',[]) if lap['driver_number']==driver and finite(lap.get('lap_duration')) and abs(lap['lap_duration']-duration)<.002]
                for lap in matching:
                    if deletion[4]=='DELETED':deleted.add((driver,lap['lap_number']))
                    else:deleted.discard((driver,lap['lap_number']))
        flag=safety or ('YELLOW' if sectors and global_flag not in ('RED','CHEQUERED') else global_flag)
        laps_by=defaultdict(list);active_by={}
        for lap in events.get('laps',[]):
            began=stamp(lap.get('date_start'))
            if began is None or began>at:continue
            number=int(lap['driver_number']);item={'lap':lap['lap_number'],'s1':None,'s2':None,'s3':None,'time':None,'deleted':(number,lap['lap_number']) in deleted,'pit_out':lap.get('is_pit_out_lap',False),'complete':False,'date_start':lap['date_start']}
            elapsed=0;known=True
            for i in range(1,4):
                duration=lap.get(f'duration_sector_{i}')
                if not finite(duration):known=False;continue
                elapsed+=duration
                # Missing earlier sectors cannot give a trustworthy sector completion clock.
                if known and began+elapsed<=at:item[f's{i}']=duration
            duration=lap.get('lap_duration')
            if finite(duration) and began+duration<=at:
                item.update(time=duration,complete=True)
                for i in range(1,4):item[f's{i}']=lap.get(f'duration_sector_{i}')
            lap_stint=next((r for r in reversed(events.get('stints',[])) if r['driver_number']==number and finite(r.get('lap_start')) and r['lap_start']<=lap['lap_number'] and (r.get('lap_end') or 9999)>=lap['lap_number']),None)
            if lap_stint:item.update(tyre_age_laps=lap_stint['tyre_age_at_start']+max(0,lap['lap_number']-lap_stint['lap_start']) if finite(lap_stint.get('tyre_age_at_start')) else None,compound=lap_stint.get('compound'),stint_number=lap_stint.get('stint_number'))
            laps_by[number].append(item)
            if number not in active_by or stamp(active_by[number]['date_start'])<began:active_by[number]=item
        best_sectors=[]
        for key in ('s1','s2','s3'):
            values=[(lap[key],number) for number,laps in laps_by.items() for lap in laps if finite(lap[key]) and not lap['deleted']]
            best_sectors.append({'time':min(values)[0],'driver_number':min(values)[1]} if values else None)
        racing=meta.get('session_type')=='Race';rows=[]
        final=events.get('session_result',[]) if phase=='FINISHED' else []
        final_by={int(r['driver_number']):r for r in final}
        best_times=[]
        for number,laps in laps_by.items():
            valid=[lap['time'] for lap in laps if finite(lap['time']) and not lap['deleted'] and not lap['pit_out']]
            if valid:best_times.append(min(valid))
        leader_time=min(best_times) if best_times else None
        for driver in data['drivers']:
            n=int(driver['driver_number']);laps=sorted(laps_by[n],key=lambda r:r['lap']);valid=[r['time'] for r in laps if finite(r['time']) and not r['deleted'] and not r['pit_out']]
            best=min(valid) if valid else None
            pos=last_at([r for r in events.get('position',[]) if r['driver_number']==n],at)
            interval=last_at([r for r in events.get('intervals',[]) if r['driver_number']==n],at) if racing else None
            active=active_by.get(n);lap_number=active['lap'] if active else 0
            stint=next((r for r in reversed(events.get('stints',[])) if r['driver_number']==n and finite(r.get('lap_start')) and r['lap_start']<=lap_number and (r.get('lap_end') or 9999)>=lap_number),None)
            tyre_age=(stint['tyre_age_at_start']+max(0,lap_number-stint['lap_start'])) if stint and finite(stint.get('tyre_age_at_start')) else None
            completion=[r for r in laps if r['complete']]
            in_pit,pit_entry=measured_pit_state(data,n,at)
            result=final_by.get(n)
            if result and not racing:
                official=result.get('duration')
                if isinstance(official,list):official=next((value for value in reversed(official) if finite(value)),None)
                if finite(official):best=official
            final_gap=result.get('gap_to_leader') if result and not racing else None
            if isinstance(final_gap,list):final_gap=next((value for value in reversed(final_gap) if value is not None),None)
            rows.append({**driver,'position':result.get('position') if result else (pos.get('position') if pos else None),'best_lap':best,'last_lap':completion[-1]['time'] if completion else None,'gap':final_gap if final_gap is not None else interval.get('gap_to_leader') if interval else (round(best-leader_time,3) if best is not None and leader_time is not None and not racing else None),'interval':interval.get('interval') if interval else None,'interval_at':interval.get('date') if interval else None,'lap':lap_number,'stint_start_lap':stint.get('lap_start') if stint else None,'tyre_age_at_start':stint.get('tyre_age_at_start') if stint else None,'pit_entry_at':pit_entry,'compound':stint.get('compound') if stint else None,'tyre_age':tyre_age,'in_pit':in_pit,'pit_status_source':'Measured lane position' if in_pit is not None else 'Unavailable','status':'DSQ' if result and result.get('dsq') else 'DNF' if result and result.get('dnf') else 'DNS' if result and result.get('dns') else None})
            rows[-1]['completed_laps']=max((lap['lap'] for lap in completion),default=0)
        # Provider positions preserve Q1/Q2/Q3 progression; comparing all-session bests would misrank eliminated cars.
        rows.sort(key=lambda r:(r['position'] is None,r['position'] or 999,r['best_lap'] or float('inf'),r['driver_number']))
        selected=next((r for r in rows if r['driver_number']==driver_number),rows[0] if rows else None)
        number=selected['driver_number'] if selected else driver_number
        personal=[min((lap[k] for lap in laps_by[number] if finite(lap[k]) and not lap['deleted']),default=None) for k in ('s1','s2','s3')]
        weather=last_at(events.get('weather',[]),at)
        # Rainfall is an observation, not a measurement of water remaining on asphalt.
        wetness=surface if surface!='UNKNOWN' else 'RAIN DETECTED' if weather and weather.get('rainfall') else 'NO RAIN DETECTED' if weather and weather.get('rainfall')==0 else 'UNKNOWN'
        winner=next((r for r in rows if r['position']==1),None) if final and phase=='FINISHED' else None
        return {'at':at,'phase':phase,'flag':flag,'hazard_sectors':sectors,'weather':weather,'surface':wetness,'rain_risk':rain_risk,'messages':controls[-8:][::-1],'rows':rows,'session_best':best_sectors,'selected':selected,'laps':sorted(laps_by[number],key=lambda r:r['lap'],reverse=True),'personal_best':personal,'ideal_lap':sum(personal) if all(finite(x) for x in personal) else None,'winner':winner,'racing':racing,'terminal_finish':terminal_finish,'_laps_by':dict(laps_by),'_controls':controls,'_pits_by':{n:[p for p in events.get('pit',[]) if p['driver_number']==n and p.get('date') and stamp(p['date'])<=at] for n in laps_by}}

class RaceControlService:
    pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='race-control')
    lock=threading.RLock();catalogs={};datasets={};live_datasets={};jobs={};live={};telemetry_jobs={};telemetry_retry={}
    cache_dir=DATA_DIR/'cache/race-control'
    provider=RaceControlProvider()
    settings=TimingSettings.environment()

    def archive_diagnostics(self,data,at):
        def state(rows,timestamp):
            dates=[timestamp(r) for r in rows];known=[t for t in dates if t is not None and t<=at]
            return {'state':'AVAILABLE' if known else 'MISSING','last_source_utc':utc_iso(max(known)) if known else None,'age_seconds':at-max(known) if known else None,'records':len(known)}
        channels={}
        for endpoint in ('laps','position','weather','race_control','stints','pit'):
            channels[endpoint]=state(data['events'].get(endpoint,[]),lambda r:utc_stamp(r.get('date') or r.get('date_start')))
        known_laps={(r['driver_number'],r['lap_number']):utc_stamp(r.get('date_start')) for r in data['events'].get('laps',[]) if r.get('date_start') and (utc_stamp(r['date_start']) or float('inf'))<=at}
        known_stints=[r for r in data['events'].get('stints',[]) if (r.get('driver_number'),r.get('lap_start')) in known_laps]
        channels['stints']={'state':'PARTIAL' if known_stints else 'MISSING','records':len(known_stints),'last_source_utc':None,'age_seconds':None,
                            'explanation':'Historical stint lap boundaries available; original publication UTC is unknown'}
        def measured(series):
            count=0;last=None
            for points in series.values():
                index=bisect.bisect_right(points,at,key=lambda p:p[0]);count+=index
                if index:last=max(last or points[index-1][0],points[index-1][0])
            return {'state':'AVAILABLE' if count else 'MISSING','last_source_utc':utc_iso(last),'age_seconds':at-last if last else None,'records':count}
        channels['positions']=measured(data['locations']);channels['telemetry']=measured(data['telemetry'])
        return {'schema_version':1,'provider_id':data.get('historical_provider','openf1_historical'),'session_key':data['meta']['session_key'],
                'state':'HISTORICAL_REPLAY','meeting_key':data['meta'].get('meeting_key'),'identity':'VERIFIED','recovered':False,'cutoff_utc':utc_iso(at),'channels':channels,
                'capabilities':{'timing':channels['laps']['state'],'positions':channels['positions']['state'],'telemetry':channels['telemetry']['state'],
                                'weather':channels['weather']['state'],'tyres':channels['stints']['state']}}

    def diagnostics(self,race_id,key,mode='LIVE',at=None):
        if not self.settings.diagnostics:raise ValueError('Feed diagnostics are disabled in configuration')
        if mode.upper() not in ('LIVE','REPLAY'):raise ValueError('Choose REPLAY or LIVE')
        if at is not None and not math.isfinite(float(at)):raise ValueError('Invalid diagnostics timestamp')
        meta=self.session(race_id,key)
        if mode.upper()=='REPLAY':
            data=self.load(key)
            if data:return self.archive_diagnostics(data,float(at) if at is not None else stamp(meta['date_start']))
        if key in self.live:
            result=self.feed_health(key).snapshot();data=self.live_data(key)
            result['buffers']={'position_samples':sum(len(p) for p in data['locations'].values()),'telemetry_samples':sum(len(p) for p in data['telemetry'].values()),'completed_laps':sum(len(p) for p in data.get('public_laps',{}).values()),'events':sum(len(p) for p in data['events'].values())} if data else {}
            result.update(meeting_key=meta.get('meeting_key'),checkpoint_error=self.live[key].get('checkpoint_error'));return result
        recovered=TimingCheckpointStore(self.cache_dir/'observed').load(meta) if self.settings.persistence else None
        if recovered:
            result=recovered['diagnostics']
            for channel in result.get('channels',{}).values():channel['state']='STALE'
            result['capabilities']={name:'STALE' for name in result.get('capabilities',{})}
            return result
        health=FeedHealth(key,self.settings);health.request(PublicTimingFeed.topics)
        return {**health.snapshot(),'meeting_key':meta.get('meeting_key')}

    def championship_projection(self,race_id,key,frame=None,mode='REPLAY',at=None,number=None,scoring='FULL_DISTANCE'):
        if not self.settings.projection:return {'status':'DISABLED','note':'Championship projection is disabled in configuration.'}
        if frame is None:
            frame=self.frame(race_id,key,at,number,mode,projection_scoring=scoring)
            return frame['championship_projection']
        return RaceControlProjectionService().project(race_id,frame,scoring)

    def stop(self,race_id,key):
        self.session(race_id,key)
        with self.lock:
            state=self.live.get(key)
            if state and state.get('client'):state['client'].stop();self.checkpoint(key,force=True)
        return {'session_key':key,'status':'DISCONNECTED'}

    @classmethod
    def shutdown(cls):
        for state in list(cls.live.values()):
            if state.get('client'):state['client'].stop()

    def live_data(self,key):
        data=self.live_datasets.get(key)
        # Backwards compatibility for callers injecting an in-memory timeline.
        # A complete historical archive must never become a live data source.
        if data is None and self.datasets.get(key) and not self.datasets[key].get('complete_archive'):
            data=self.datasets[key]
        return data

    def feed_health(self,key):
        state=self.live.setdefault(key,{'status':'DISCONNECTED','last_message':None})
        return state.setdefault('health',FeedHealth(key,self.settings))

    def race_info(self,race_id):
        with SessionLocal() as s:
            race=s.get(Race,race_id)
            if race is None:raise ValueError('Unknown race')
            circuit=s.get(Circuit,race.circuit_id)
            return race.to_dict(),CircuitPresentationService().present(circuit)

    def catalog(self,race_id,refresh=False):
        race,circuit=self.race_info(race_id);now=utcnow()
        cached=self.catalogs.get(race_id)
        rows=[];error=None
        if cached and not refresh and time.monotonic()-cached['checked']<600:rows=cached['rows'];error=cached.get('error')
        elif race['season_year']>=2023:
            day=parse_time(race['date']+'T00:00:00+00:00')
            try:
                raw=self.provider.fetch('sessions',{'year':race['season_year']})
                raw=[r for r in raw if day-timedelta(days=3)<=parse_time(r['date_start'])<day+timedelta(days=1)]
                gps=[r for r in raw if r.get('session_name')=='Race' and parse_time(r['date_start']).date()==day.date()]
                if len(gps)==1:rows=[r for r in raw if r.get('meeting_key')==gps[0]['meeting_key'] and r.get('session_name') in CODES and not r.get('is_cancelled')]
                else:error='No verified OpenF1 meeting matches this race date.'
            except Exception as exc:rows=cached['rows'] if cached else [];error=str(exc)
            self.catalogs[race_id]={'rows':rows,'checked':time.monotonic(),'error':error}
        else:error='Position and timing coverage starts in 2023.'
        sessions=[]
        for row in sorted(rows,key=lambda r:r['date_start']):
            start=parse_time(row['date_start']);end=parse_time(row['date_end']);key=row['session_key']
            active_data=self.live_data(key) or {}
            health=self.live.get(key,{}).get('health')
            active=active_data.get('public_state',{}).get('SessionStatus',{}).get('Status')=='Started' and health is not None and health.snapshot()['state']=='LIVE'
            finish_observed=self.live.get(key,{}).get('finished_at')
            live_end=max(end+timedelta(minutes=30),parse_time(finish_observed)+timedelta(minutes=30)) if finish_observed else end+timedelta(minutes=30)
            state='UPCOMING' if now<start else 'LIVE_WINDOW' if now<=live_end or active else 'REPLAY'
            sessions.append({**row,'circuit_length_km':circuit.get('length_km'), 'code':CODES[row['session_name']],'state':state,'live_allowed':start<=now and (now<=live_end or active),'replay_allowed':state=='REPLAY','archive_at':iso(end+timedelta(minutes=30)),'prepared':bool(self.datasets.get(key,{}).get('complete_archive')) or self.path(key).exists()})
        return {'race':race,'circuit':circuit,'sessions':sessions,'live_configured':self.settings.enabled,'provider':'OpenF1','source_url':'https://openf1.org/docs/','error':error,'as_of':iso(now),'access_note':'Free public live timing. Position and car channels depend on what the public source transmits. Complete recorded sessions use the free OpenF1 archive.'}

    def session(self,race_id,key):
        item=next((r for r in self.catalog(race_id)['sessions'] if r['session_key']==key),None)
        if item is None:raise ValueError('This timing session does not belong to the selected race')
        return item

    def path(self,key):return self.cache_dir/f'{int(key)}-v1.json.gz'

    def load(self,key):
        if key not in self.datasets and self.path(key).exists():
            with gzip.open(self.path(key),'rt') as f:self.datasets[key]=json.load(f)
            # Keep a handful of complete sessions resident; files remain available.
            while len(self.datasets)>4:
                oldest=next(iter(self.datasets))
                if oldest==key:break
                self.datasets.pop(oldest,None)
        data=self.datasets.get(key)
        if data:
            track_sectors(data);add_track_landmarks(data)
        if data and not data.get('_media_checked'):
            data['drivers']=self.enrich_drivers(data['drivers']);data['_media_checked']=True
        if data and data.get('complete_archive') and not data.get('_extent_checked'):
            time_extent(data);data['_extent_checked']=True
        return data

    def covered(self,data):
        return bool(data and data.get('complete_archive') and data.get('coverage_end',stamp(data['meta']['date_end'])+300)>=stamp(data['meta'].get('timeline_end') or data['meta']['date_end']))

    def enrich_drivers(self,rows):
        import unicodedata
        def normalized(value):return ''.join(c for c in unicodedata.normalize('NFKD',value or '').casefold() if c.isalnum())
        with SessionLocal() as s:
            drivers=s.query(Driver).all();by_name={normalized((d.forename or '')+' '+(d.surname or '')):d for d in drivers};by_code=defaultdict(list)
            for d in drivers:
                if d.code:by_code[d.code].append(d)
            output=[]
            for row in rows:
                name=row.get('name') or ((row.get('first_name') or '')+' '+(row.get('last_name') or '')).strip() or row.get('full_name')
                code=row.get('name_acronym') or row.get('code') or str(row['driver_number'])
                # Driver codes are reused across seasons (e.g. VER: Vergne / Verstappen).
                d=by_name.get(normalized(name))
                if d is None and len(by_code[code])==1:d=by_code[code][0]
                media=MediaService().get(d.driver_id) if d else {}
                color=row.get('team_colour') or (row.get('color') or '').lstrip('#') or '939AA6';color=color if re.fullmatch(r'[A-Fa-f0-9]{6}',color) else '939AA6'
                output.append({'driver_number':int(row['driver_number']),'code':code,'name':name,'team':row.get('team_name') or row.get('team'),'color':'#'+color,'image':media.get('driver_image') or row.get('headshot_url') or row.get('image')})
            return sorted(output,key=lambda d:d['code'])

    def compact_locations(self,rows):
        grouped=defaultdict(list)
        for r in rows:
            t=stamp(r.get('date'))
            if t is not None and finite(r.get('x')) and finite(r.get('y')) and (r['x'] or r['y']):grouped[str(r['driver_number'])].append([t,r['x'],r['y']])
        compact={}
        for key,values in grouped.items():
            values.sort();last=-1e20;out=[]
            for point in values:
                if point[0]-last>=.45:out.append(point);last=point[0]
            compact[key]=out
        return compact

    def prepare(self,race_id,key,mode):
        meta=self.session(race_id,key);mode=mode.upper()
        if mode not in ('REPLAY','LIVE'):raise ValueError('Choose REPLAY or LIVE')
        if mode=='REPLAY' and not meta['replay_allowed']:raise ValueError('Replay becomes available after the live access window ends')
        if mode=='LIVE' and not meta['live_allowed']:
            raise ValueError('Live opens at the session start and uses only the public timing feed')
        job_key=f'{key}-{mode}'
        with self.lock:
            old=self.jobs.get(job_key)
            if old and old['status'] in ('QUEUED','RUNNING'):return copy.deepcopy(old)
            if mode=='REPLAY' and self.load(key) and self.covered(self.load(key)):return {'status':'SUCCESS','session_key':key,'mode':mode,'progress':'Replay ready'}
            if mode=='LIVE' and key in self.live and self.live[key].get('client') and self.live[key]['status'] not in ('DISCONNECTED','PROVIDER_UNAVAILABLE','ACCESS_DENIED','SESSION_ENDED'):
                return {'status':'SUCCESS','session_key':key,'mode':mode,'progress':'Shared live connection already started'}
            job={'status':'QUEUED','session_key':key,'mode':mode,'progress':'Preparing timing'};self.jobs[job_key]=job
        def work():
            job['status']='RUNNING'
            try:
                if mode=='LIVE':
                    self.prepare_public(key,meta);job.update(status='SUCCESS',progress='Connection started; observations determine live availability');return
                data={'meta':meta,'drivers':[],'events':{},'locations':{},'telemetry':{},'track':None,'downloaded_at':iso(utcnow()),'complete_archive':mode=='REPLAY'}
                if not self.settings.openf1_historical:raise ValueError('OpenF1 historical loading is disabled')
                job['progress']='Loading drivers and timing'
                data['drivers']=self.enrich_drivers(self.provider.fetch('drivers',{'session_key':key}))
                if not data['drivers']:raise ValueError('Driver timing is not available for this session yet. Try again shortly.')
                endpoints=['laps','position','stints','weather','race_control','pit']+(['intervals'] if meta['session_type']=='Race' else [])
                for endpoint in endpoints:
                    job['progress']='Loading '+endpoint.replace('_',' ')
                    data['events'][endpoint]=sorted_rows(self.provider.fetch(endpoint,{'session_key':key}))
                if mode=='REPLAY':
                    data['events']['session_result']=self.provider.fetch('session_result',{'session_key':key})
                    time_extent(data)
                    locations=[];start=parse_time(data['meta']['timeline_start']);end=parse_time(data['meta']['timeline_end'])+timedelta(minutes=5)
                    while start<end:
                        stop=min(start+timedelta(minutes=15),end);job['progress']='Loading measured positions · '+start.strftime('%H:%M UTC')
                        locations.extend(self.provider.fetch('location',{'session_key':key,'date>':start.strftime('%Y-%m-%dT%H:%M:%S'),'date<':stop.strftime('%Y-%m-%dT%H:%M:%S')}));start=stop
                    data['locations']=self.compact_locations(locations);data['track']=make_track(data);track_sectors(data);add_track_landmarks(data);data['coverage_end']=end.timestamp();data['_extent_checked']=True
                    # Timing-only archives are useful too; never fabricate missing coordinates.
                    self.cache_dir.mkdir(parents=True,exist_ok=True)
                    temporary=self.path(key).with_suffix('.tmp')
                    with gzip.open(temporary,'wt') as f:json.dump(data,f,separators=(',',':'))
                    temporary.replace(self.path(key));self.datasets[key]=data
                job.update(status='SUCCESS',progress='Replay ready' if mode=='REPLAY' else 'Live connection started')
            except Exception as exc:
                if mode=='REPLAY' and self.settings.fastf1_historical and self.settings.multi_provider:
                    try:
                        race,_=self.race_info(race_id);job['progress']='Trying verified FastF1 historical archive'
                        enriched={**meta,'year':race['season_year'],'round':race['round']}
                        data=FastF1RaceControlArchive().build(enriched);data['drivers']=self.enrich_drivers(data['drivers'])
                        time_extent(data);data['track']=make_track(data);track_sectors(data);add_track_landmarks(data)
                        data['coverage_end']=stamp(data['meta']['timeline_end'])+300;data['_extent_checked']=True
                        self.cache_dir.mkdir(parents=True,exist_ok=True);temporary=self.path(key).with_suffix('.tmp')
                        with gzip.open(temporary,'wt') as f:json.dump(data,f,separators=(',',':'),allow_nan=False)
                        temporary.replace(self.path(key));self.datasets[key]=data
                        job.update(status='SUCCESS',progress='FastF1 measured replay ready',source='fastf1_historical',primary_source_error=str(exc));return
                    except Exception as fallback:job['fallback_error']='Historical fallback unavailable ('+type(fallback).__name__+')'
                job.update(status='FAILED',error=str(exc),progress='Connection unavailable')
        self.pool.submit(work)
        return copy.deepcopy(job)

    def prepare_public(self,key,meta):
        # Keep connections bounded across a local session selector/popout.
        active=[k for k,v in self.live.items() if k!=key and v.get('client') and v.get('status') not in ('DISCONNECTED','SESSION_ENDED','ACCESS_DENIED','PROVIDER_UNAVAILABLE')]
        if len(active)>=2:
            oldest=min(active,key=lambda k:self.live[k].get('started',0));self.live[oldest]['client'].stop();self.checkpoint(oldest,force=True)
        previous_live=self.live.get(key)
        if previous_live and previous_live.get('client'):previous_live['client'].stop()
        data={'meta':meta,'drivers':[],'events':{},'locations':{},'telemetry':{},'track':None,'downloaded_at':iso(utcnow()),'complete_archive':False,'public_state':{},'public_laps':{},'public_pit_entries':{},'source':'Formula 1 public SignalR'}
        for other in self.catalogs.values():
            for previous in other['rows']:
                if previous.get('meeting_key')==meta['meeting_key']:
                    archive=self.load(previous['session_key'])
                    if archive and archive.get('complete_archive') and archive.get('track'):
                        data['track']=copy.deepcopy(archive['track']);break
        recovered=TimingCheckpointStore(self.cache_dir/'observed').load(meta) if self.settings.persistence else None
        if recovered:
            data=recovered['data'];data.update(meta=meta,recovered=True)
            # A matching checkpoint may preserve observed lap history/current
            # state. Its old source timestamps remain STALE; a new socket alone
            # cannot make those observations live.
        self.live_datasets[key]=data
        while len(self.live_datasets)>3:
            expired=min((k for k in self.live_datasets if k!=key),key=lambda k:self.live.get(k,{}).get('started',0))
            previous=self.live.get(expired,{})
            if previous.get('client'):previous['client'].stop();self.checkpoint(expired,force=True)
            self.live_datasets.pop(expired,None);self.live.pop(expired,None)
        state={'status':'CONNECTING','error':None,'last_message':None,'client':None,'started':time.monotonic()};self.live[key]=state
        health=self.feed_health(key);data['_ledger']=PatchLedger(key)
        if recovered:
            health.recovered=True;health.channels=copy.deepcopy(recovered['diagnostics'].get('channels',{}))
            data['_ledger'].fields=data.pop('ledger_fields',{})
        feed=PublicTimingFeed(key,lambda topic,patch,date:self.ingest_public(key,topic,patch,date),lambda status,error:state.update(status=status,error=error),expected=meta,health=health)
        state['client']=feed
        feed.start()
        def monitor():
            while not feed.cancel.wait(30) and time.monotonic()-state['started']<6*3600:
                finished=state.get('finished_at')
                if finished and (utcnow()-parse_time(finished)).total_seconds()>1800:break
            feed.stop()
            if state.get('finished_at'):health.transport('SESSION_ENDED');state.update(status='SESSION_ENDED')
            self.checkpoint(key,force=True)
        # A daemon supervisor does not occupy the archive/telemetry download worker.
        threading.Thread(target=monitor,name=f'public-timing-{key}',daemon=True).start()

    def ingest_public(self,key,topic,patch,date=None):
        data=self.live_data(key)
        if data is None:return
        now=utcnow().timestamp();source=utc_stamp(date,assume_utc=True);event_date=utc_iso(source);health=self.feed_health(key)
        earliest=(utc_stamp(data['meta'].get('date_start')) or 0)-1800 # Same tolerance as verified session start context.
        if date is not None and (source is None or source>now or source<earliest and topic not in ('SessionInfo','DriverList')):health.observe(topic,source,now,valid=False);return
        with self.lock:
            self.live[key]['last_message']=utc_iso(now)
            if topic in ('Position.z','CarData.z'):
                try:decoded=decode_channel(patch)
                except ValueError:health.observe(topic,source,now,valid=False);return
                latest=None;valid=0
                roster={d['driver_number'] for d in data['drivers']}
                if topic=='Position.z':
                    for packet in indexed(decoded.get('Position',[])):
                        if not isinstance(packet,dict) or not isinstance(packet.get('Entries'),dict):continue
                        t=utc_stamp(packet.get('Timestamp'),assume_utc=True)
                        if t is None or t>now or t<earliest:continue
                        for n,p in packet.get('Entries',{}).items():
                            if not str(n).isdigit() or int(n) not in roster or not isinstance(p,dict):continue
                            x=numeric(p.get('X'),-1e7,1e7);y=numeric(p.get('Y'),-1e7,1e7)
                            if x is None or y is None or x==y==0:continue
                            self.ingest(key,'location',{'driver_number':int(n),'date':utc_iso(t),'x':x,'y':y});latest=max(latest or t,t);valid+=1
                else:
                    for packet in indexed(decoded.get('Entries',[])):
                        if not isinstance(packet,dict) or not isinstance(packet.get('Cars'),dict):continue
                        t=utc_stamp(packet.get('Utc'),assume_utc=True)
                        if t is None or t>now or t<earliest:continue
                        for n,car in packet.get('Cars',{}).items():
                            if not str(n).isdigit() or int(n) not in roster or not isinstance(car,dict):continue
                            c=car.get('Channels',{})
                            if not isinstance(c,dict):continue
                            values={field:numeric(c.get(channel),lo,hi) for field,channel,lo,hi in [('rpm','0',0,20000),('speed','2',0,450),('n_gear','3',0,8),('throttle','4',0,100),('brake','5',0,100),('drs','45',0,14)]}
                            if isinstance(c.get('5'),bool):values['brake']=100. if c['5'] else 0.
                            for field in ('n_gear','drs'):
                                if values[field] is not None and not values[field].is_integer():values[field]=None
                            if not any(v is not None for v in values.values()):continue
                            self.ingest(key,'car_data',{'driver_number':int(n),'date':utc_iso(t),**values});latest=max(latest or t,t);valid+=1
                health.observe(topic,latest,now,valid=bool(valid));self.checkpoint(key)
                return
            old=data['public_state'].get(topic,{})
            ledger=data.setdefault('_ledger',PatchLedger(key))
            merged,changed,duplicate=ledger.apply(topic,old,patch,source,now)
            timing_valid=True
            if topic=='TimingData':
                roster={str(d['driver_number']) for d in data.get('drivers',[])}
                incoming=patch.get('Lines',{}) if isinstance(patch,dict) else {}
                timing_valid=isinstance(incoming,dict) and any(str(n) in roster and isinstance(line,dict) and any(field in line for field in ('Position','Line','NumberOfLaps','LastLapTime','BestLapTime','Sectors','InPit','GapToLeader','IntervalToPositionAhead','Retired','Stopped')) for n,line in incoming.items())
            channel_source=source
            if topic=='RaceControlMessages' and channel_source is None and isinstance(merged,dict):
                times=[utc_stamp(r.get('Utc'),assume_utc=True) for r in indexed(merged.get('Messages')) if isinstance(r,dict)]
                channel_source=max((t for t in times if t is not None and t<=now),default=None)
            health.observe(topic,channel_source,now,valid=changed and timing_valid,duplicate=duplicate)
            if not changed:return
            if topic=='TimingData' and timing_valid and source is not None and now-source<=self.settings.stale_seconds and health.identity=='VERIFIED':
                health.recovered=False;data['recovered']=False
            data['public_state'][topic]=merged
            merged=data['public_state'][topic]
            if topic=='SessionInfo' and merged.get('SessionStatus')=='Finalised':self.live[key]['finished_at']=event_date
            elif topic=='DriverList':
                rows=[{'driver_number':int(n),'name_acronym':p.get('Tla'),'first_name':p.get('FirstName'),'last_name':p.get('LastName'),'full_name':p.get('FullName'),'team_name':p.get('TeamName'),'team_colour':p.get('TeamColour'),'headshot_url':p.get('HeadshotUrl')} for n,p in merged.items() if str(n).isdigit() and 1<=int(n)<=999 and isinstance(p,dict) and (p.get('RacingNumber') is None or str(p['RacingNumber'])==str(n))]
                data['drivers']=self.enrich_drivers(rows)
            elif topic=='RaceControlMessages':
                rows=[]
                for r in indexed(merged.get('Messages')):
                    if not isinstance(r,dict):continue
                    message_at=utc_stamp(r.get('Utc'),assume_utc=True)
                    if message_at is None or message_at>now or message_at<earliest:continue
                    rows.append({'date':utc_iso(message_at),'message':r.get('Message'),'category':r.get('Category'),'flag':r.get('Flag'),'scope':r.get('Scope'),'sector':r.get('Sector'),'driver_number':r.get('RacingNumber'),'message_id':r.get('MessageId'),'source':'existing_public_timing'})
                data['events']['race_control']=sorted_rows(rows)[-self.settings.max_events:]
            elif topic=='WeatherData':
                fields=[('air_temperature','AirTemp',-30,80),('track_temperature','TrackTemp',-30,100),('humidity','Humidity',0,100),('wind_speed','WindSpeed',0,100),('wind_direction','WindDirection',0,360),('rainfall','Rainfall',0,1)]
                provenance={name:ledger.provenance('WeatherData.'+path,now) for name,path,_,_ in fields}
                values={name:numeric(merged.get(path),lo,hi) if provenance[name] and provenance[name]['age_seconds'] is not None and provenance[name]['age_seconds']<=self.settings.stale_seconds else None for name,path,lo,hi in fields}
                if event_date:self.ingest(key,'weather',{'date':event_date,**values,'wind_speed_unit':'m/s','source':'existing_public_timing','provenance':provenance})
            elif topic=='SessionStatus':
                status=merged.get('Status');message={'Started':'SESSION STARTED','Aborted':'SESSION ABORTED','Finished':'SESSION FINISHED','Ends':'SESSION FINISHED','Finalised':'SESSION FINISHED'}.get(status)
                if message and event_date:self.ingest(key,'race_control',{'date':event_date,'category':'SessionStatus','message':message})
                if status=='Started':self.live[key].pop('finished_at',None)
                elif status in ('Finished','Ends','Finalised') and (data['meta'].get('session_type')=='Race' or data['public_state'].get('SessionInfo',{}).get('SessionStatus')=='Finalised'):self.live[key]['finished_at']=event_date
            elif topic=='TimingAppData':
                for n,application in merged.get('Lines',{}).items():
                    if not isinstance(application,dict):continue
                    current=indexed(application.get('Stints'));before=indexed((old.get('Lines',{}).get(n) or {}).get('Stints'))
                    # A newly observed stint can be anchored to the current lap;
                    # StartLaps in the source is starting tyre AGE, not a race lap.
                    if event_date and before and len(current)>len(before):
                        line=data['public_state'].get('TimingData',{}).get('Lines',{}).get(n) or {}
                        count=line.get('NumberOfLaps')
                        if isinstance(count,int):data.setdefault('public_stint_starts',{}).setdefault(n,{})[str(len(current)-1)]=count+1
            elif topic=='TimingData':
                for n,line in merged.get('Lines',{}).items():
                    if not str(n).isdigit() or not isinstance(line,dict):continue
                    previous=old.get('Lines',{}).get(n,{})
                    entries=data.setdefault('public_pit_entries',{})
                    if previous and line.get('InPit') is True and previous.get('InPit') is False and event_date:
                        entries[n]=event_date;self.ingest(key,'pit',{'date':event_date,'driver_number':int(n),'source':'Observed InPit transition','pit_duration':None})
                    if line.get('InPit') is False:entries.pop(n,None)
                    raw_count=numeric(line.get('NumberOfLaps'),0,300);previous_count=numeric(previous.get('NumberOfLaps'),0,300)
                    count=int(raw_count) if raw_count is not None else 0;last=seconds(line.get('LastLapTime'))
                    # Keep genuinely observed completed laps after connection. Do not infer past sectors from the latest snapshot.
                    if event_date and count and previous_count is not None and count==int(previous_count)+1 and previous and last is not None:
                        sector_values=[seconds(r.get('Value')) if isinstance(r,dict) else None for r in indexed(line.get('Sectors'))][:3]
                        if len(sector_values)!=3 or not all(finite(v) for v in sector_values) or abs(sum(sector_values)-last)>.15:sector_values=[None,None,None]
                        observed_stints=indexed(data['public_state'].get('TimingAppData',{}).get('Lines',{}).get(n,{}).get('Stints'))
                        observed_stint=observed_stints[-1] if observed_stints and isinstance(observed_stints[-1],dict) else {}
                        history=data['public_laps'].setdefault(n,[])
                        if not any(l['lap']==count for l in history):history.append({'lap':count,'s1':sector_values[0],'s2':sector_values[1],'s3':sector_values[2],'time':last,'complete':True,'deleted':False,'pit_out':bool(line.get('PitOut')),'date_start':utc_iso(source-last),'date_end':event_date,'track_flag':data['public_state'].get('TrackStatus',{}).get('Status'),'tyre_age_laps':observed_stint.get('TotalLaps'),'compound':observed_stint.get('Compound'),'stint_number':len(observed_stints),'source':'existing_public_timing'})
                        history[:]=history[-self.settings.max_laps:]
                        self.ingest(key,'laps',{'driver_number':int(n),'lap_number':count,'date_start':utc_iso(source-last),'lap_duration':last,
                            'duration_sector_1':sector_values[0],'duration_sector_2':sector_values[1],'duration_sector_3':sector_values[2],'is_pit_out_lap':bool(line.get('PitOut'))})
                        if not data.get('track'):
                            data['track']=make_track(data)
                            if data['track']:track_sectors(data);add_track_landmarks(data)
            self.checkpoint(key)

    def checkpoint(self,key,force=False):
        data=self.live_data(key);state=self.live.get(key,{})
        if not self.settings.persistence or data is None or not data.get('meta',{}).get('session_key') or not force and time.monotonic()-state.get('checkpoint_tick',0)<5:return
        state['checkpoint_tick']=time.monotonic()
        try:
            TimingCheckpointStore(self.cache_dir/'observed').save(data,self.feed_health(key).snapshot())
            state['checkpoint_error']=None
        except (ValueError,OSError):state['checkpoint_error']='Unable to persist bounded timing checkpoint'

    def public_frame(self,data,frame,number):
        state=data['public_state'];lines=state.get('TimingData',{}).get('Lines',{});apps=state.get('TimingAppData',{}).get('Lines',{});rows=[]
        racing=data['meta']['session_type']=='Race'
        ledger=data.get('_ledger');cutoff=frame['at'];key=data['meta']['session_key']
        quality=self.feed_health(key).snapshot(cutoff)
        if frame.get('weather'):
            weather=copy.deepcopy(frame['weather']);age=cutoff-(utc_stamp(weather.get('date')) or cutoff)
            weather.update(age_seconds=max(0,age),state='STALE' if age>self.settings.stale_seconds else 'AVAILABLE')
            for field in ('air_temperature','track_temperature','humidity','wind_speed','wind_direction','rainfall'):
                field_source=utc_stamp((weather.get('provenance',{}).get(field) or {}).get('observed_utc'))
                if age>self.settings.stale_seconds or field_source is not None and cutoff-field_source>self.settings.stale_seconds:weather[field]=None
            frame['weather']=weather
            if weather.get('rainfall') is None and frame.get('surface') in ('RAIN DETECTED','NO RAIN DETECTED'):frame['surface']='UNKNOWN'
        histories={n:[copy.deepcopy(l) for l in history if l.get('date_end') and (utc_stamp(l['date_end']) or float('inf'))<=cutoff] for n,history in data.get('public_laps',{}).items()}
        for message in frame.get('_controls',[]):
            deletion=re.search(r'CAR (\d+).*TIME (\d+):(\d+\.\d+) (DELETED|REINSTATED)',(message.get('message') or '').upper())
            if deletion:
                duration=int(deletion[2])*60+float(deletion[3])
                for lap in histories.get(deletion[1],[]):
                    if finite(lap.get('time')) and abs(lap['time']-duration)<.002:lap['deleted']=deletion[4]=='DELETED'
        def rawgap(value):
            if isinstance(value,dict):value=value.get('Value')
            if value is None or value=='' or isinstance(value,bool):return None
            try:
                number=float(str(value).lstrip('+'));return number if math.isfinite(number) else None
            except ValueError:return value
        for driver in data['drivers']:
            n=str(driver['driver_number']);line=lines.get(n) or {};application=apps.get(n) or {};stints=indexed(application.get('Stints'));stint=stints[-1] if stints and isinstance(stints[-1],dict) else {};stats=indexed(line.get('Stats'));part=int(state.get('TimingData',{}).get('SessionPart') or 1);stat=stats[part-1] if 0<part<=len(stats) and isinstance(stats[part-1],dict) else {}
            position=numeric(line.get('Position') or line.get('Line'),1,30);position=int(position) if position is not None and position.is_integer() else None
            field_paths={'position':'Position','best_lap':'BestLapTime.Value','last_lap':'LastLapTime.Value','lap':'NumberOfLaps','gap':'GapToLeader','interval':'IntervalToPositionAhead.Value','in_pit':'InPit','status':'Retired'}
            provenance={field:ledger.provenance('TimingData.Lines.'+n+'.'+path,cutoff) if ledger else None for field,path in field_paths.items()}
            stint_index=max(0,len(stints)-1);start_lap=data.get('public_stint_starts',{}).get(n,{}).get(str(stint_index));age=numeric(stint.get('TotalLaps'),0,300)
            for field,path in [('compound','Compound'),('tyre_age','TotalLaps')]:provenance[field]=ledger.provenance(f'TimingAppData.Lines.{n}.Stints.{stint_index}.{path}',cutoff) if ledger else None
            for field,path in [('gap','GapToLeader'),('position','Line')]:
                if not provenance.get(field):provenance[field]=ledger.provenance('TimingData.Lines.'+n+'.'+path,cutoff) if ledger else None
            interval_at=(provenance['interval'] or provenance['gap'] or {}).get('observed_utc')
            best_lap=seconds(line.get('BestLapTime'))
            if best_lap is None:best_lap=seconds((state.get('TimingStats',{}).get('Lines',{}).get(n) or {}).get('PersonalBestLapTime'))
            observed_count=numeric(line.get('NumberOfLaps'),0,300)
            rows.append({**driver,'position':position,'best_lap':best_lap,'last_lap':seconds(line.get('LastLapTime')),'gap':rawgap(line.get('GapToLeader')) if racing else rawgap(stat.get('TimeDiffToFastest')),'interval':rawgap(line.get('IntervalToPositionAhead')) if racing else None,'interval_at':interval_at,'lap':int(observed_count) if observed_count is not None else None,'stint_start_lap':start_lap,'tyre_age_at_start':stint.get('StartLaps'),'pit_entry_at':data.get('public_pit_entries',{}).get(n),'compound':stint.get('Compound'),'tyre_age':age,'in_pit':line.get('InPit') if isinstance(line.get('InPit'),bool) else None,'status':'DNF' if line.get('Retired') is True else 'STOP' if line.get('Stopped') is True else None,'provenance':provenance,'timing_state':quality['channels'].get('TimingData',{}).get('state','MISSING')})
            rows[-1]['completed_laps']=int(observed_count) if observed_count is not None else None
            stops=line.get('NumberOfPitStops');observed=[p for p in data['events'].get('pit',[]) if p.get('driver_number')==driver['driver_number'] and (utc_stamp(p.get('date')) or float('inf'))<=cutoff]
            rows[-1].update(pit_stops=stops if isinstance(stops,int) else len(observed) if observed else None,pit_stops_source='Published timing count' if isinstance(stops,int) else 'Entries observed since connection',pit_events=observed[-12:])
        rows.sort(key=lambda r:(r['position'] is None,r['position'] or 999,r['driver_number']))
        if not racing:
            known=[r['best_lap'] for r in rows if finite(r['best_lap'])];leader=min(known) if known else None
            for r in rows:
                if r['gap'] is None and r['best_lap'] is not None and leader is not None:r['gap']=round(r['best_lap']-leader,3)
        selected=next((r for r in rows if r['driver_number']==number),rows[0] if rows else None)
        laps=histories.get(str(number),[]);personal=[min((lap[k] for lap in laps if finite(lap[k]) and not lap.get('deleted')),default=None) for k in ('s1','s2','s3')]
        best=[]
        for k in ('s1','s2','s3'):
            values=[(lap[k],int(n)) for n,history in histories.items() for lap in history if finite(lap[k]) and not lap.get('deleted')]
            best.append({'time':min(values)[0],'driver_number':min(values)[1]} if values else None)
        # BestSectors is an observed aggregate, never a reconstructed lap.
        aggregate=state.get('TimingStats',{}).get('Lines',{})
        for index in range(3):
            values=[]
            for n,line in aggregate.items():
                if not str(n).isdigit() or not isinstance(line,dict):continue
                slots=indexed(line.get('BestSectors'));value=seconds(slots[index]) if index<len(slots) else None
                if value is not None:values.append((value,int(n)))
            if values and (best[index] is None or min(values)[0]<best[index]['time']):best[index]={'time':min(values)[0],'driver_number':min(values)[1],'source':'TimingStats aggregate'}
            selected_slots=indexed((aggregate.get(str(number)) or {}).get('BestSectors'));value=seconds(selected_slots[index]) if index<len(selected_slots) else None
            if value is not None and (personal[index] is None or value<personal[index]):personal[index]=value
        track_status=state.get('TrackStatus',{}).get('Status');flags={'1':'GREEN','2':'YELLOW','4':'SAFETY CAR','5':'RED','6':'VSC','7':'VSC · ENDING'}
        if track_status in flags:frame['flag']=flags[track_status]
        session_status=state.get('SessionStatus',{}).get('Status')
        final_status=state.get('SessionInfo',{}).get('SessionStatus')=='Finalised'
        frame['phase']={'Started':'RUNNING','Aborted':'SUSPENDED','Finished':'FINISHED' if final_status else 'FINISHING' if racing else 'BREAK','Ends':'FINISHED' if final_status else 'FINISHING' if racing else 'BREAK','Finalised':'FINISHED'}.get(session_status,frame['phase'])
        if frame['phase']=='FINISHED':frame['flag']='CHEQUERED'
        # A transport finality flag does not confirm the published result.
        final=data['public_state'].get('SessionInfo',{}).get('SessionStatus')=='Finalised'
        winner=None # Finalised describes session closure, not an independently verified winner.
        frame.update(rows=rows,selected=selected,laps=sorted(laps,key=lambda r:r['lap'],reverse=True),personal_best=personal,ideal_lap=sum(personal) if all(finite(v) for v in personal) else None,session_best=best,winner=winner,source='Formula 1 public SignalR',positions_available=bool(data['locations']),telemetry_available=bool(data['telemetry']),_laps_by={int(n):history for n,history in histories.items()},diagnostics=quality,history_note='Lap history and sector bests are collected since connection; previous laps are available in the completed-session replay.')
        return frame

    def ingest(self,key,endpoint,row):
        with self.lock:
            data=self.live_data(key);state=self.live[key]
            if data is None:return
            state['last_message']=iso(utcnow())
            if endpoint=='location':
                t=stamp(row.get('date'));n=str(row.get('driver_number'));points=data['locations'].setdefault(n,[])
                if t and finite(row.get('x')) and finite(row.get('y')) and (row['x'] or row['y']) and (not points or t-points[-1][0]>=.45):points.append([t,row['x'],row['y']])
                points[:]=points[-self.settings.max_position_samples:]
                if not data['track'] and len(points)%150==0:data['track']=make_track(data)
            elif endpoint=='car_data':
                n=str(row.get('driver_number'));points=data['telemetry'].setdefault(n,[]);t=stamp(row.get('date'))
                if t and (not points or t-points[-1][0]>=.45):points.append([t,row.get('speed'),row.get('n_gear'),row.get('throttle'),row.get('brake'),row.get('drs'),row.get('rpm')]);points[:]=points[-self.settings.max_car_samples:]
            else:
                rows=data['events'].setdefault(endpoint,[])
                if endpoint=='laps':rows[:]=[r for r in rows if (r.get('driver_number'),r.get('lap_number'))!=(row.get('driver_number'),row.get('lap_number'))]
                elif endpoint=='stints':rows[:]=[r for r in rows if (r.get('driver_number'),r.get('stint_number'))!=(row.get('driver_number'),row.get('stint_number'))]
                elif endpoint=='session_result':rows[:]=[r for r in rows if r.get('driver_number')!=row.get('driver_number')]
                if rows and (stamp(row.get('date')) or 0)<(stamp(rows[-1].get('date')) or 0):
                    bisect.insort_right(rows,row,key=lambda r:stamp(r.get('date')) or 0)
                elif not rows or row!=rows[-1]:rows.append(row)
                rows[:]=rows[-self.settings.max_events:]

    def status(self,race_id,key,mode):
        self.session(race_id,key)
        job=copy.deepcopy(self.jobs.get(f'{key}-{mode.upper()}',{'status':'IDLE','progress':'Choose Start live or Load replay'}))
        state=self.live.get(key)
        if state:
            health=self.feed_health(key).snapshot();job['connection']={'status':health['state'],'error':health['error'],'last_message':state.get('last_message')}
        return job

    def telemetry(self,data,number):
        key=data['meta']['session_key'];job_key=(key,number)
        if str(number) in data['telemetry'] or self.telemetry_jobs.get(job_key)=='LOADING' or time.monotonic()<self.telemetry_retry.get(job_key,0):return
        self.telemetry_jobs[job_key]='LOADING'
        def work():
            try:
                file=self.cache_dir/f'{key}-car-{number}.json.gz'
                if file.exists():
                    with gzip.open(file,'rt') as f:values=json.load(f)
                else:
                    raw=self.provider.fetch('car_data',{'session_key':key,'driver_number':number});values=[];last=-1e20
                    for r in sorted_rows(raw):
                        t=stamp(r.get('date'))
                        if t and t-last>=.45:values.append([t,r.get('speed'),r.get('n_gear'),r.get('throttle'),r.get('brake'),r.get('drs'),r.get('rpm')]);last=t
                    self.cache_dir.mkdir(parents=True,exist_ok=True)
                    with gzip.open(file,'wt') as f:json.dump(values,f,separators=(',',':'))
                with self.lock:data['telemetry'][str(number)]=values
                self.telemetry_jobs[job_key]='READY'
            except Exception:
                self.telemetry_jobs[job_key]='ERROR';self.telemetry_retry[job_key]=time.monotonic()+60
        self.pool.submit(work)

    def frame(self,race_id,key,at,number,mode,window=30,projection_scoring='FULL_DISTANCE'):
        meta=self.session(race_id,key);mode=mode.upper()
        if mode not in ('LIVE','REPLAY'):raise ValueError('Choose REPLAY or LIVE')
        if mode=='REPLAY' and not meta['replay_allowed']:raise ValueError('This session is not archived yet')
        data=self.live_data(key) if mode=='LIVE' else self.load(key)
        if not data:raise ValueError('Load this session before requesting timing')
        if mode=='REPLAY' and not self.covered(data):raise ValueError('Load the archived session for a complete replay')
        if mode=='LIVE':
            if not meta['live_allowed']:raise ValueError('This session has ended. Use the free historical replay.')
            if key not in self.live:raise ValueError('Start the live connection first')
            at=utcnow().timestamp() # All model inputs and public fields share this cutoff.
        else:at=float(at) if at is not None else stamp(meta['date_start'])
        if not math.isfinite(at):raise ValueError('Invalid replay timestamp')
        window=max(20,min(240,int(window)))
        if not data['drivers']:number=None
        elif not number:number=data['drivers'][0]['driver_number']
        if number is not None and number not in {d['driver_number'] for d in data['drivers']}:raise ValueError('Unknown driver for this session')
        if mode=='REPLAY' and number is not None:self.telemetry(data,number)
        with self.lock:
            frame=TimingTimeline.frame(data,at,number)
            if mode=='LIVE':frame=self.public_frame(data,frame,number)
            else:
                for row in frame['rows']:
                    pits=[p for p in frame.get('_pits_by',{}).get(row['driver_number'],[]) if (utc_stamp(p.get('date')) or float('inf'))<=at]
                    row.update(pit_stops=len(pits),pit_stops_source='Historical pit events',pit_events=pits[-12:])
            history=frame.get('_laps_by',{})
            strategy=RaceStrategyService();strategy.build_flags(frame.get('_controls',[]))
            def observed_flag(lap):
                began=utc_stamp(lap.get('date_start'));finished=utc_stamp(lap.get('date_end')) or (began+lap['time'] if began is not None and finite(lap.get('time')) else None)
                if began is None or finished is None:return lap.get('track_flag')
                values=[strategy._flag_at([],began),strategy._flag_at([],finished)]+strategy.flag_values[bisect.bisect_right(strategy.flag_times,began):bisect.bisect_left(strategy.flag_times,finished)]
                return 'GREEN' if values and all(f in ('GREEN','CLEAR') for f in values) else 'UNKNOWN'
            frame['laps_for_projection']={str(n):[{'complete':l.get('complete'),'track_flag':observed_flag(l),'lap':l.get('lap')} for l in laps] for n,laps in history.items()}
            frame['meta']=meta
            frame['result_confirmation']=confirm_result(race_id,frame,mode)
            frame['scheduled_laps']=data.get('public_state',{}).get('LapCount',{}).get('TotalLaps')
            frame=RaceStrategyService().enrich(frame,data,meta.get('circuit_length_km') or 5.)
            locations={n:series_window(points,frame['at']-8,frame['at']+window if mode=='REPLAY' else frame['at']) for n,points in data['locations'].items()}
            if mode=='LIVE':locations={n:[p for p in points if p[0]<=frame['at']] for n,points in locations.items()}
            frame.update(meta={**data['meta'],'circuit_length_km':meta.get('circuit_length_km')},mode=mode,track=data['track'],position_window_s=window,locations=locations,telemetry=[p for p in series_window(data['telemetry'].get(str(number),[]),frame['at']-60,frame['at']) if p[0]<=frame['at']],telemetry_status='READY' if str(number) in data['telemetry'] else 'UNAVAILABLE' if mode=='LIVE' or self.telemetry_jobs.get((key,number))=='ERROR' else 'LOADING',downloaded_at=data['downloaded_at'])
            if mode=='LIVE':
                health=frame['diagnostics'];frame['connection']={'status':health['state'],'error':health['error'],'last_message':self.live[key].get('last_message')}
                if health['state']!='LIVE' and frame['racing'] and frame['phase']!='FINISHED':
                    frame['race_forecast']={'status':'STALE_INPUTS','note':'Live estimates are paused until dated, matching timing observations arrive.','model_version':RaceStrategyService.version,'feature_cutoff':frame['at']}
            else:frame['diagnostics']=self.archive_diagnostics(data,frame['at'])
            frame['championship_projection']=self.championship_projection(race_id,key,frame=frame,scoring=projection_scoring)
            if mode=='LIVE' and frame['connection']['status']!='LIVE' and frame['championship_projection'].get('drivers'):
                frame['championship_projection'].update(status='STALE_INPUTS',note='Last-known order only; fresh live timing is not available. This projection is not current.')
            frame.pop('laps_for_projection',None)
        return frame

atexit.register(RaceControlService.shutdown)
