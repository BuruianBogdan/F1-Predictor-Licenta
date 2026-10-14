"""Synthetic bounded-buffer stress test; deliberately not live source evidence."""
import _bootstrap
import json,time,tracemalloc
from services.race_control_service import RaceControlService
from data_sources.timing_contract import TimingSettings,utc_iso


def main():
    service=RaceControlService();service.settings=TimingSettings(persistence=False)
    service.live={999:{'last_message':None}}
    data={'meta':{'session_key':999},'events':{},'locations':{},'telemetry':{},'track':{'points':[]}}
    service.live_datasets={999:data};now=time.time()-20000
    tracemalloc.start();began=time.perf_counter();cpu=time.process_time()
    for i in range(4500):
        date=utc_iso(now+i)
        for n in range(1,23):
            service.ingest(999,'location',{'driver_number':n,'date':date,'x':100+i%200,'y':200})
            service.ingest(999,'car_data',{'driver_number':n,'date':date,'speed':200,'rpm':12000})
        service.ingest(999,'weather',{'date':date,'air_temperature':29})
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    report={'status':'TESTED_FIXTURE','virtual_seconds':4500,'drivers':22,'events_injected':202500,
            'elapsed_seconds':time.perf_counter()-began,'cpu_seconds':time.process_time()-cpu,
            'python_allocated_bytes':current,'python_peak_allocated_bytes':peak,
            'position_samples':sum(map(len,data['locations'].values())),
            'telemetry_samples':sum(map(len,data['telemetry'].values())),
            'weather_events':len(data['events']['weather']),
            'bound_check':all(len(p)==1800 for p in data['locations'].values()) and all(len(p)==500 for p in data['telemetry'].values()) and len(data['events']['weather'])==4000,'live_evidence':False}
    assert report['bound_check']
    (_bootstrap.ROOT/'docs/LIVE_BUFFER_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
