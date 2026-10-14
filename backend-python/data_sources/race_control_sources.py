"""Source roles and a genuine historical fallback, composed with existing providers.

The compared GitHub clients share an upstream. Running them all would create
duplicate connections, not independent observations. No external live adapter
is silently enabled by configuration.
"""
import os
from typing import Protocol
from data_sources.fastf1_provider import FastF1Provider
from data_sources.base_provider import ProviderError
from data_sources.timing_contract import utc_stamp,utc_iso,numeric


class HistoricalProvider(Protocol):
    def fetch(self,endpoint,params=None): ...


class StreamingProvider(Protocol):
    def start(self): ...
    def stop(self): ...


def provider_catalog():
    return {'providers':[
        {'id':'existing_public_timing','role':'primary_live','transport':'SignalR Core',
         'enabled':os.getenv('LIVE_ENABLED','true').lower() in ('true','1','yes'),
         'capabilities':['timing','sectors','tyres','weather','race_control','lap_count','track_status'],
         'conditional_capabilities':['positions','telemetry'],'availability':'UNKNOWN_UNTIL_OBSERVED',
         'documentation':'https://github.com/theOehrly/Fast-F1'},
        {'id':'openf1_historical','role':'primary_historical','transport':'rate-limited REST',
         'enabled':os.getenv('OPENF1_HISTORICAL_ENABLED','true').lower() in ('true','1','yes'),
         'capabilities':['timing','positions','telemetry','tyres','weather','race_control'],
         'availability':'PER_SESSION','documentation':'https://openf1.org/docs/'},
        {'id':'fastf1_historical','role':'historical_fallback','transport':'cached historical session files',
         'enabled':os.getenv('FASTF1_HISTORICAL_ENABLED','true').lower() in ('true','1','yes'),
         'capabilities':['timing','positions','telemetry','tyres','weather','race_control'],
         'availability':'PER_SESSION','documentation':'https://docs.fastf1.dev/'},
        {'id':'jolpica_official','role':'published_classification_and_standings','transport':'existing REST sync',
         'enabled':True,'capabilities':['published_results','championship_baseline'],
         'documentation':'https://github.com/jolpica/jolpica-f1'},
        {'id':'external_live_adapter','role':'optional_live','enabled':False,'availability':'NOT_TESTED',
         'reason':'No tested independent public live advantage. Referenced clients share the same upstream.'}],
        'parallel_live_connections_per_session':1,'multi_provider_policy':'Historical fallback and published results enrich existing Race Control; live channels are never filled with historical positions.'}


class FastF1RaceControlArchive:
    """Convert FastF1's *measured* session into the existing replay schema."""
    def build(self,meta):
        import pandas as pd
        api=FastF1Provider()._api()
        name={'Race':'R','Sprint':'S','Qualifying':'Q','Sprint Qualifying':'SQ','Sprint Shootout':'SQ',
              'Practice 1':'FP1','Practice 2':'FP2','Practice 3':'FP3'}.get(meta['session_name'])
        if name is None:raise ProviderError('FastF1 does not support this session type')
        selected=api.get_session(meta['year'],meta['round'],name)
        selected.load(laps=True,telemetry=True,weather=True,messages=True)
        session_date=pd.Timestamp(selected.date)
        if session_date.tzinfo is None:session_date=session_date.tz_localize('UTC')
        if abs(session_date.timestamp()-utc_stamp(meta['date_start']))>1800:
            raise ProviderError('FastF1 historical session does not match the selected calendar time')
        zero=pd.Timestamp(selected.t0_date)
        if zero.tzinfo is None:zero=zero.tz_localize('UTC')
        def absolute(value):
            if pd.isna(value):return None
            if isinstance(value,pd.Timedelta):return utc_iso((zero+value).timestamp())
            t=pd.Timestamp(value);t=t.tz_localize('UTC') if t.tzinfo is None else t
            return utc_iso(t.timestamp())
        def duration(value):return value.total_seconds() if not pd.isna(value) else None
        drivers=[];events={'laps':[],'position':[],'stints':[],'weather':[],'race_control':[], 'pit':[],'session_result':[],'intervals':[]};locations={};telemetry={}
        for _,r in selected.results.iterrows():
            n=int(r['DriverNumber']);drivers.append({'driver_number':n,'code':r.get('Abbreviation'),'name':r.get('FullName'),
                'team':r.get('TeamName'),'color':'#'+str(r.get('TeamColor') or '939AA6')})
            pos=numeric(r.get('Position'),1,30);status=str(r.get('Status') or '')
            events['session_result'].append({'driver_number':n,'position':int(pos) if pos else None,
                                            'dnf':status not in ('Finished','') and '+' not in status,'dsq':'Disqualified' in status,'dns':'Did not start' in status})
        for _,r in selected.laps.iterrows():
            n=int(r['DriverNumber']);lap=int(r['LapNumber']);start=absolute(r.get('LapStartDate'))
            event={'driver_number':n,'lap_number':lap,'date_start':start,'lap_duration':duration(r.get('LapTime')),
                   'is_pit_out_lap':not pd.isna(r.get('PitOutTime'))}
            for i in (1,2,3):event['duration_sector_'+str(i)]=duration(r.get('Sector'+str(i)+'Time'))
            events['laps'].append(event)
            date=absolute(r.get('Time'));pos=numeric(r.get('Position'),1,30)
            if pos and date:events['position'].append({'driver_number':n,'date':date,'position':int(pos)})
            if not pd.isna(r.get('PitInTime')):events['pit'].append({'driver_number':n,'date':absolute(r['PitInTime']),'lap_number':lap,'pit_duration':None})
            if not pd.isna(r.get('Stint')):
                stint=int(r['Stint']);existing=next((s for s in events['stints'] if s['driver_number']==n and s['stint_number']==stint),None)
                age=numeric(r.get('TyreLife'),0,300)
                if existing:existing['lap_end']=max(existing['lap_end'],lap)
                else:events['stints'].append({'driver_number':n,'stint_number':stint,'lap_start':lap,'lap_end':lap,'compound':r.get('Compound'), 'tyre_age_at_start':max(0,age-1) if age is not None else None})
        for _,r in selected.weather_data.iterrows():
            events['weather'].append({'date':absolute(r['Time']),'air_temperature':numeric(r.get('AirTemp'),-30,80),
                'track_temperature':numeric(r.get('TrackTemp'),-30,100),'humidity':numeric(r.get('Humidity'),0,100),
                'wind_speed':numeric(r.get('WindSpeed'),0,100),'wind_speed_unit':'m/s','wind_direction':numeric(r.get('WindDirection'),0,360),
                'rainfall':float(r['Rainfall']) if not pd.isna(r.get('Rainfall')) else None})
        for _,r in selected.race_control_messages.iterrows():
            date=absolute(r['Time'])
            events['race_control'].append({'date':date,'message':r.get('Message'),'flag':r.get('Flag'), 'scope':r.get('Scope'),
                'sector':numeric(r.get('Sector'),1,50),'driver_number':numeric(r.get('RacingNumber'),1,999),'category':r.get('Category')})
        for _,r in selected.session_status.iterrows():
            status=r.get('Status');message={'Started':'SESSION STARTED','Finished':'SESSION FINISHED','Ends':'SESSION ENDED','Aborted':'SESSION ABORTED'}.get(status)
            if message:events['race_control'].append({'date':absolute(r['Time']),'message':message,'category':'SessionStatus'})
        valid_numbers={str(d['driver_number']) for d in drivers}
        for n,values in selected.pos_data.items():
            if str(n) not in valid_numbers:continue
            points=[];last=0
            for _,r in values.iterrows():
                date=absolute(r['Date']);t=utc_stamp(date);x=numeric(r.get('X'),-1e7,1e7);y=numeric(r.get('Y'),-1e7,1e7)
                if t and t-last>=.45 and x is not None and y is not None and (x or y):points.append([t,x,y]);last=t
            locations[str(n)]=points
        for n,values in selected.car_data.items():
            if str(n) not in valid_numbers:continue
            points=[];last=0
            for _,r in values.iterrows():
                t=utc_stamp(absolute(r['Date']))
                if t and t-last>=.45:
                    points.append([t,numeric(r.get('Speed'),0,450),numeric(r.get('nGear'),0,8),numeric(r.get('Throttle'),0,100),
                                   100. if not pd.isna(r.get('Brake')) and bool(r.get('Brake')) else 0. if not pd.isna(r.get('Brake')) else None,numeric(r.get('DRS'),0,14),numeric(r.get('RPM'),0,20000)]);last=t
            telemetry[str(n)]=points
        for rows in events.values():rows.sort(key=lambda r:utc_stamp(r.get('date') or r.get('date_start')) or 0)
        return {'meta':meta,'drivers':drivers,'events':events,'locations':locations,'telemetry':telemetry,'track':None,
                'downloaded_at':utc_iso(pd.Timestamp.now(tz='UTC').timestamp()),'complete_archive':True,
                'historical_provider':'fastf1_historical','source':'FastF1 measured historical session'}
