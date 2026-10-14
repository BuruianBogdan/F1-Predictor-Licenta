"""Measured local frame, serialization, contention and checkpoint costs."""
import _bootstrap
import copy,json,time,statistics,tempfile,threading,tracemalloc
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from services.race_control_service import RaceControlService
from services.race_control_checkpoint import TimingCheckpointStore


def main():
    s=RaceControlService();catalog=s.catalog(209);meta=next(m for m in catalog['sessions'] if m['code']=='R');key=meta['session_key'];at=datetime.fromisoformat('2026-10-04T09:14:40+00:00').timestamp()
    s.load(key);original=s.lock;waits=[];holds=[];local=threading.local()
    class TimedLock:
        def __enter__(self):
            began=time.perf_counter();original.acquire();waits.append(time.perf_counter()-began);local.started=time.perf_counter()
        def __exit__(self,*args):holds.append(time.perf_counter()-local.started);original.release()
    s.lock=TimedLock();frames=[];serial=[];payloads=[]
    def run(i):
        began=time.perf_counter();f=s.frame(209,key,at,16,'REPLAY');frames.append((time.perf_counter()-began)*1000)
        began=time.perf_counter();p=json.dumps(f,separators=(',',':'),allow_nan=False);serial.append((time.perf_counter()-began)*1000);payloads.append(len(p.encode()))
    tracemalloc.start()
    with ThreadPoolExecutor(2) as pool:list(pool.map(run,range(30)))
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    data=s.load(key);bounded={k:copy.deepcopy(v) for k,v in data.items() if k in ('meta','drivers','downloaded_at','public_state')};bounded.update(events={k:v[-4000:] for k,v in data['events'].items() if k!='session_result'},locations={n:v[-1800:] for n,v in data['locations'].items()},telemetry={n:v[-500:] for n,v in data['telemetry'].items()})
    store=TimingCheckpointStore(Path(tempfile.mkdtemp(prefix='f1-checkpoint-perf-')));began=time.perf_counter();store.save(bounded,{});save_ms=(time.perf_counter()-began)*1000
    path=store.path(key)
    def stats(values):return {'p50':statistics.median(values),'p95':sorted(values)[int(len(values)*.95)-1],'max':max(values)}
    report={'status':'VERIFIED_HISTORICAL','verified_at':datetime.now(timezone.utc).isoformat(),'two_concurrent_viewer_workers':2,'frames':len(frames),'frame_ms':stats(frames),'serialization_ms':stats(serial),'payload_bytes':stats(payloads),'lock_wait_ms':stats([v*1000 for v in waits]),'lock_held_ms':stats([v*1000 for v in holds]),'traced_allocations_bytes':current,'traced_peak_bytes':peak,'checkpoint_bounded_historical_sample':{'gzip_bytes':path.stat().st_size,'save_ms':save_ms},'active_live_connections':sum(1 for v in s.live.values() if v.get('client') and v.get('status') not in ('DISCONNECTED','SESSION_ENDED','ACCESS_DENIED','PROVIDER_UNAVAILABLE')),'limitations':['Local historical replay contention experiment, allocation tracing adds overhead.','No broadcast or network end-to-end latency measured; no active live race.','Checkpoint sample is bounded real historical data, not a live ingestion trace.']}
    (_bootstrap.ROOT/'docs/LIVE_PERFORMANCE_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
