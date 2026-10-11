"""Real timing timeline. Replay and live share the same timestamp-filtered rendering."""
import bisect,copy,gzip,json,math,re,threading,time
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

CODES={'Practice 1':'FP1','Practice 2':'FP2','Practice 3':'FP3','Sprint Qualifying':'SQ','Sprint Shootout':'SQ','Sprint':'SPRINT','Qualifying':'Q','Race':'R'}

def stamp(value):
    return parse_time(value).timestamp() if value else None

def finite(value):return isinstance(value,(float,int)) and math.isfinite(value)

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
        return {'points':[[p[1],p[2]] for p in points],'bounds':[min(xs),min(ys),max(xs),max(ys)],'source':'OpenF1 measured lap trajectory','driver_number':lap['driver_number'],'lap':lap['lap_number']}
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
            lap_stint=next((r for r in reversed(events.get('stints',[])) if r['driver_number']==number and r['lap_start']<=lap['lap_number'] and (r.get('lap_end') or 9999)>=lap['lap_number']),None)
            if lap_stint:item.update(tyre_age_laps=(lap_stint.get('tyre_age_at_start') or 0)+max(0,lap['lap_number']-lap_stint['lap_start']),compound=lap_stint.get('compound'),stint_number=lap_stint.get('stint_number'))
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
            stint=next((r for r in reversed(events.get('stints',[])) if r['driver_number']==n and r['lap_start']<=lap_number and (r.get('lap_end') or 9999)>=lap_number),None)
            tyre_age=(stint.get('tyre_age_at_start',0)+max(0,lap_number-stint['lap_start'])) if stint else None
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
    lock=threading.RLock();catalogs={};datasets={};jobs={};live={};telemetry_jobs={};telemetry_retry={}
    cache_dir=DATA_DIR/'cache/race-control'
    provider=RaceControlProvider()

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
            active_data=self.datasets.get(key,{})
            active=active_data.get('public_state',{}).get('SessionStatus',{}).get('Status')=='Started'
            finish_observed=self.live.get(key,{}).get('finished_at')
            live_end=max(end+timedelta(minutes=30),parse_time(finish_observed)+timedelta(minutes=30)) if finish_observed else end+timedelta(minutes=30)
            state='UPCOMING' if now<start else 'LIVE_WINDOW' if now<=live_end or active else 'REPLAY'
            sessions.append({**row,'circuit_length_km':circuit.get('length_km'), 'code':CODES[row['session_name']],'state':state,'live_allowed':start<=now and (now<=live_end or active),'replay_allowed':state=='REPLAY','archive_at':iso(end+timedelta(minutes=30)),'prepared':bool(self.datasets.get(key,{}).get('complete_archive')) or self.path(key).exists()})
        return {'race':race,'circuit':circuit,'sessions':sessions,'live_configured':True,'provider':'OpenF1','source_url':'https://openf1.org/docs/','error':error,'as_of':iso(now),'access_note':'Free public live timing. Position and car channels depend on what the public source transmits. Complete recorded sessions use the free OpenF1 archive.'}

    def session(self,race_id,key):
        item=next((r for r in self.catalog(race_id)['sessions'] if r['session_key']==key),None)
        if item is None:raise ValueError('This timing session does not belong to the selected race')
        return item

    def path(self,key):return self.cache_dir/f'{int(key)}-v1.json.gz'

    def load(self,key):
        if key not in self.datasets and self.path(key).exists():
            with gzip.open(self.path(key),'rt') as f:self.datasets[key]=json.load(f)
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
            if mode=='LIVE' and key in self.live and self.live[key]['status']=='CONNECTED':return {'status':'SUCCESS','session_key':key,'mode':mode,'progress':'Live connected'}
            job={'status':'QUEUED','session_key':key,'mode':mode,'progress':'Preparing timing'};self.jobs[job_key]=job
        def work():
            job['status']='RUNNING'
            try:
                if mode=='LIVE':
                    self.prepare_public(key,meta);job.update(status='SUCCESS',progress='Public live timing connected');return
                data={'meta':meta,'drivers':[],'events':{},'locations':{},'telemetry':{},'track':None,'downloaded_at':iso(utcnow()),'complete_archive':mode=='REPLAY'}
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
                    if not data['locations']:raise ValueError('OpenF1 has no position feed for this session.')
                    self.cache_dir.mkdir(parents=True,exist_ok=True)
                    temporary=self.path(key).with_suffix('.tmp')
                    with gzip.open(temporary,'wt') as f:json.dump(data,f,separators=(',',':'))
                    temporary.replace(self.path(key));self.datasets[key]=data
                job.update(status='SUCCESS',progress='Replay ready' if mode=='REPLAY' else 'Live connection started')
            except Exception as exc:job.update(status='FAILED',error=str(exc),progress='Connection unavailable')
        self.pool.submit(work)
        return copy.deepcopy(job)

    def prepare_public(self,key,meta):
        previous_live=self.live.get(key)
        if previous_live and previous_live.get('client'):previous_live['client'].stop()
        data={'meta':meta,'drivers':[],'events':{},'locations':{},'telemetry':{},'track':None,'downloaded_at':iso(utcnow()),'complete_archive':False,'public_state':{},'public_laps':{},'public_pit_entries':{},'source':'Formula 1 public SignalR'}
        for other in self.catalogs.values():
            for previous in other['rows']:
                if previous.get('meeting_key')==meta['meeting_key']:
                    archive=self.load(previous['session_key'])
                    if archive and archive.get('complete_archive') and archive.get('track'):
                        data['track']=copy.deepcopy(archive['track']);break
        self.datasets[key]=data
        state={'status':'CONNECTING','error':None,'last_message':None,'client':None,'started':time.monotonic()};self.live[key]=state
        feed=PublicTimingFeed(key,lambda topic,patch,date:self.ingest_public(key,topic,patch,date),lambda status,error:state.update(status=status,error=error))
        state['client']=feed.start()
        def monitor():
            while time.monotonic()-state['started']<6*3600:
                time.sleep(30)
                finished=state.get('finished_at')
                if finished and (utcnow()-parse_time(finished)).total_seconds()>1800:break
            feed.stop();state.update(status='ENDED')
        # A daemon supervisor does not occupy the archive/telemetry download worker.
        threading.Thread(target=monitor,name=f'public-timing-{key}',daemon=True).start()

    def ingest_public(self,key,topic,patch,date=None):
        import base64,zlib
        data=self.datasets[key];now=iso(utcnow());event_date=date if date and 'T' in str(date) else now
        with self.lock:
            self.live[key]['last_message']=now
            if topic in ('Position.z','CarData.z'):
                try:decoded=json.loads(zlib.decompress(base64.b64decode(patch),-zlib.MAX_WBITS))
                except (ValueError,TypeError,zlib.error):return
                if topic=='Position.z':
                    for packet in decoded.get('Position',[]):
                        for n,p in packet.get('Entries',{}).items():
                            self.ingest(key,'location',{'driver_number':int(n),'date':packet['Timestamp'],'x':p.get('X'),'y':p.get('Y')})
                else:
                    for packet in decoded.get('Entries',[]):
                        for n,car in packet.get('Cars',{}).items():
                            c=car.get('Channels',{});self.ingest(key,'car_data',{'driver_number':int(n),'date':packet['Utc'],'speed':c.get('2'),'n_gear':c.get('3'),'throttle':c.get('4'),'brake':c.get('5'),'drs':c.get('45')})
                return
            old=data['public_state'].get(topic,{})
            data['public_state'][topic]=merge_patch(old,patch)
            merged=data['public_state'][topic]
            if topic=='SessionInfo' and merged.get('SessionStatus')=='Finalised':self.live[key]['finished_at']=event_date
            elif topic=='DriverList':
                rows=[{'driver_number':int(n),'name_acronym':p.get('Tla'),'first_name':p.get('FirstName'),'last_name':p.get('LastName'),'full_name':p.get('FullName'),'team_name':p.get('TeamName'),'team_colour':p.get('TeamColour'),'headshot_url':p.get('HeadshotUrl')} for n,p in merged.items() if n.isdigit() and isinstance(p,dict)]
                data['drivers']=self.enrich_drivers(rows)
            elif topic=='RaceControlMessages':
                rows=[]
                for r in indexed(merged.get('Messages')):
                    rows.append({'date':r.get('Utc'),'message':r.get('Message'),'category':r.get('Category'),'flag':r.get('Flag'),'scope':r.get('Scope'),'sector':r.get('Sector')})
                data['events']['race_control']=sorted_rows(rows)
            elif topic=='WeatherData':
                def num(k):
                    try:return float(merged[k])
                    except (KeyError,TypeError,ValueError):return None
                self.ingest(key,'weather',{'date':event_date,'air_temperature':num('AirTemp'),'track_temperature':num('TrackTemp'),'humidity':num('Humidity'),'wind_speed':num('WindSpeed'),'wind_direction':num('WindDirection'),'rainfall':num('Rainfall')})
            elif topic=='SessionStatus':
                status=merged.get('Status');message={'Started':'SESSION STARTED','Aborted':'SESSION ABORTED','Finished':'SESSION FINISHED','Ends':'SESSION FINISHED','Finalised':'SESSION FINISHED'}.get(status)
                if message:self.ingest(key,'race_control',{'date':event_date,'category':'SessionStatus','message':message})
                if status=='Started':self.live[key].pop('finished_at',None)
                elif status in ('Finished','Ends','Finalised') and (data['meta'].get('session_type')=='Race' or data['public_state'].get('SessionInfo',{}).get('SessionStatus')=='Finalised'):self.live[key]['finished_at']=event_date
            elif topic=='TimingData':
                for n,line in merged.get('Lines',{}).items():
                    if not str(n).isdigit():continue
                    previous=old.get('Lines',{}).get(n,{})
                    entries=data.setdefault('public_pit_entries',{})
                    if previous and line.get('InPit') and not previous.get('InPit'):entries[n]=event_date
                    if not line.get('InPit'):entries.pop(n,None)
                    count=int(line.get('NumberOfLaps') or 0);last=seconds(line.get('LastLapTime'))
                    # Keep genuinely observed completed laps after connection. Do not infer past sectors from the latest snapshot.
                    if count and count>int(previous.get('NumberOfLaps') or 0) and previous and last is not None:
                        sector_values=[seconds(r.get('Value')) for r in indexed(line.get('Sectors'))][:3]
                        if len(sector_values)!=3 or not all(finite(v) for v in sector_values) or abs(sum(sector_values)-last)>.15:sector_values=[None,None,None]
                        observed_stints=indexed(data['public_state'].get('TimingAppData',{}).get('Lines',{}).get(n,{}).get('Stints'))
                        observed_stint=observed_stints[-1] if observed_stints else {}
                        data['public_laps'].setdefault(n,[]).append({'lap':count,'s1':sector_values[0],'s2':sector_values[1],'s3':sector_values[2],'time':last,'complete':True,'deleted':False,'pit_out':False,'date_end':event_date,'track_flag':data['public_state'].get('TrackStatus',{}).get('Status'),'tyre_age_laps':observed_stint.get('TotalLaps'),'compound':observed_stint.get('Compound'),'stint_number':len(observed_stints)})

    def public_frame(self,data,frame,number):
        state=data['public_state'];lines=state.get('TimingData',{}).get('Lines',{});apps=state.get('TimingAppData',{}).get('Lines',{});rows=[]
        racing=data['meta']['session_type']=='Race'
        def rawgap(value):
            if isinstance(value,dict):value=value.get('Value')
            if value is None or value=='':return None
            try:return float(str(value).lstrip('+'))
            except ValueError:return value
        for driver in data['drivers']:
            n=str(driver['driver_number']);line=lines.get(n,{});stints=indexed(apps.get(n,{}).get('Stints'));stint=stints[-1] if stints else {};stats=indexed(line.get('Stats'));part=int(state.get('TimingData',{}).get('SessionPart') or 1);stat=stats[min(part-1,len(stats)-1)] if stats else {}
            position=line.get('Position') or line.get('Line');position=int(position) if position and str(position).isdigit() else None
            rows.append({**driver,'position':position,'best_lap':seconds(line.get('BestLapTime')),'last_lap':seconds(line.get('LastLapTime')),'gap':rawgap(line.get('GapToLeader')) if racing else rawgap(stat.get('TimeDiffToFastest')),'interval':rawgap(line.get('IntervalToPositionAhead')) if racing else None,'interval_at':self.live[data['meta']['session_key']]['last_message'],'lap':line.get('NumberOfLaps') or 0,'stint_start_lap':None,'tyre_age_at_start':None,'pit_entry_at':data.get('public_pit_entries',{}).get(n),'compound':stint.get('Compound'),'tyre_age':stint.get('TotalLaps'),'in_pit':bool(line.get('InPit')),'status':'DNF' if line.get('Retired') else 'STOP' if line.get('Stopped') else None})
        rows.sort(key=lambda r:(r['position'] is None,r['position'] or 999,r['driver_number']))
        if not racing:
            known=[r['best_lap'] for r in rows if finite(r['best_lap'])];leader=min(known) if known else None
            for r in rows:
                if r['gap'] is None and r['best_lap'] is not None and leader is not None:r['gap']=round(r['best_lap']-leader,3)
        selected=next((r for r in rows if r['driver_number']==number),rows[0] if rows else None)
        laps=data['public_laps'].get(str(number),[]);personal=[min((lap[k] for lap in laps if finite(lap[k])),default=None) for k in ('s1','s2','s3')]
        best=[]
        for k in ('s1','s2','s3'):
            values=[(lap[k],int(n)) for n,history in data['public_laps'].items() for lap in history if finite(lap[k])]
            best.append({'time':min(values)[0],'driver_number':min(values)[1]} if values else None)
        track_status=state.get('TrackStatus',{}).get('Status');flags={'1':'GREEN','2':'YELLOW','4':'SAFETY CAR','5':'RED','6':'VSC','7':'VSC · ENDING'}
        if track_status in flags:frame['flag']=flags[track_status]
        session_status=state.get('SessionStatus',{}).get('Status')
        final_status=state.get('SessionInfo',{}).get('SessionStatus')=='Finalised'
        frame['phase']={'Started':'RUNNING','Aborted':'SUSPENDED','Finished':'FINISHED' if final_status else 'FINISHING' if racing else 'BREAK','Ends':'FINISHED' if final_status else 'FINISHING' if racing else 'BREAK','Finalised':'FINISHED'}.get(session_status,frame['phase'])
        if frame['phase']=='FINISHED':frame['flag']='CHEQUERED'
        # SessionInfo.Finalised provides explicit finality; a provisional P1 is never announced as the winner.
        final=data['public_state'].get('SessionInfo',{}).get('SessionStatus')=='Finalised'
        winner=next((r for r in rows if r['position']==1),None) if final and frame['phase']=='FINISHED' else None
        frame.update(rows=rows,selected=selected,laps=sorted(laps,key=lambda r:r['lap'],reverse=True),personal_best=personal,ideal_lap=sum(personal) if all(finite(v) for v in personal) else None,session_best=best,winner=winner,source='Formula 1 public SignalR',positions_available=bool(data['locations']),telemetry_available=bool(data['telemetry']),_laps_by={int(n):history for n,history in data['public_laps'].items()},history_note='Lap history and sector bests are collected since connection; previous laps are available in the completed-session replay.')
        return frame

    def ingest(self,key,endpoint,row):
        with self.lock:
            data=self.datasets[key];state=self.live[key];state['last_message']=iso(utcnow())
            if endpoint=='location':
                t=stamp(row.get('date'));n=str(row.get('driver_number'));points=data['locations'].setdefault(n,[])
                if t and finite(row.get('x')) and finite(row.get('y')) and (row['x'] or row['y']) and (not points or t-points[-1][0]>=.45):points.append([t,row['x'],row['y']])
                if not data['track'] and len(points)%150==0:data['track']=make_track(data)
            elif endpoint=='car_data':
                n=str(row.get('driver_number'));points=data['telemetry'].setdefault(n,[]);t=stamp(row.get('date'))
                if t and (not points or t-points[-1][0]>=.45):points.append([t,row.get('speed'),row.get('n_gear'),row.get('throttle'),row.get('brake'),row.get('drs')]);points[:]=points[-500:]
            else:
                rows=data['events'].setdefault(endpoint,[])
                if endpoint=='laps':rows[:]=[r for r in rows if (r.get('driver_number'),r.get('lap_number'))!=(row.get('driver_number'),row.get('lap_number'))]
                elif endpoint=='stints':rows[:]=[r for r in rows if (r.get('driver_number'),r.get('stint_number'))!=(row.get('driver_number'),row.get('stint_number'))]
                elif endpoint=='session_result':rows[:]=[r for r in rows if r.get('driver_number')!=row.get('driver_number')]
                rows.append(row);rows.sort(key=lambda r:stamp(r.get('date')) or 0)

    def status(self,race_id,key,mode):
        self.session(race_id,key)
        job=copy.deepcopy(self.jobs.get(f'{key}-{mode.upper()}',{'status':'IDLE','progress':'Choose Start live or Load replay'}))
        state=self.live.get(key)
        if state:job['connection']={k:v for k,v in state.items() if k in ('status','error','last_message')}
        return job

    def telemetry(self,data,number):
        key=data['meta']['session_key'];job_key=(key,number)
        if str(number) in data['telemetry'] or self.telemetry_jobs.get(job_key) in ('LOADING','READY') or time.monotonic()<self.telemetry_retry.get(job_key,0):return
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
                        if t and t-last>=.45:values.append([t,r.get('speed'),r.get('n_gear'),r.get('throttle'),r.get('brake'),r.get('drs')]);last=t
                    self.cache_dir.mkdir(parents=True,exist_ok=True)
                    with gzip.open(file,'wt') as f:json.dump(values,f,separators=(',',':'))
                with self.lock:data['telemetry'][str(number)]=values
                self.telemetry_jobs[job_key]='READY'
            except Exception:
                self.telemetry_jobs[job_key]='ERROR';self.telemetry_retry[job_key]=time.monotonic()+60
        self.pool.submit(work)

    def frame(self,race_id,key,at,number,mode,window=30):
        meta=self.session(race_id,key);mode=mode.upper()
        if mode not in ('LIVE','REPLAY'):raise ValueError('Choose REPLAY or LIVE')
        if mode=='REPLAY' and not meta['replay_allowed']:raise ValueError('This session is not archived yet')
        data=self.load(key)
        if not data:raise ValueError('Load this session before requesting timing')
        if mode=='REPLAY' and not self.covered(data):raise ValueError('Load the archived session for a complete replay')
        if mode=='LIVE':
            if not meta['live_allowed']:raise ValueError('This session has ended. Use the free historical replay.')
            if key not in self.live:raise ValueError('Start the live connection first')
            at=utcnow().timestamp()-5 # short interpolation buffer, never forecast car movement
        else:at=float(at) if at is not None else stamp(meta['date_start'])
        if not math.isfinite(at):raise ValueError('Invalid replay timestamp')
        window=max(20,min(240,int(window)))
        if not number:number=data['drivers'][0]['driver_number']
        if number not in {d['driver_number'] for d in data['drivers']}:raise ValueError('Unknown driver for this session')
        if mode=='REPLAY':self.telemetry(data,number)
        with self.lock:
            frame=TimingTimeline.frame(data,at,number)
            if mode=='LIVE':frame=self.public_frame(data,frame,number)
            frame=RaceStrategyService().enrich(frame,data,meta.get('circuit_length_km') or 5.)
            frame.update(meta={**data['meta'],'circuit_length_km':meta.get('circuit_length_km')},mode=mode,track=data['track'],position_window_s=window,locations={n:series_window(points,frame['at']-6,frame['at']+window) for n,points in data['locations'].items()},telemetry=series_window(data['telemetry'].get(str(number),[]),frame['at']-60,frame['at']),telemetry_status='READY' if str(number) in data['telemetry'] else 'UNAVAILABLE' if mode=='LIVE' or self.telemetry_jobs.get((key,number))=='ERROR' else 'LOADING',downloaded_at=data['downloaded_at'])
            if mode=='LIVE':frame['connection']={k:v for k,v in self.live[key].items() if k in ('status','error','last_message')}
        return frame
