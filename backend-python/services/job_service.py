"""Small local single-worker queue for explicit admin operations."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import logging,uuid
from services.season_service import iso,utcnow

class JobService:
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='f1-admin')
    lock=Lock();jobs={}
    @classmethod
    def submit(cls,label,operation):
        with cls.lock:
            if any(j['status'] in ('QUEUED','RUNNING') for j in cls.jobs.values()):raise ValueError('An admin operation is already running')
            job_id=uuid.uuid4().hex
            cls.jobs[job_id]={'id':job_id,'label':label,'status':'QUEUED','started_at':iso(utcnow())}
        def run():
            cls.jobs[job_id]['status']='RUNNING'
            try:cls.jobs[job_id].update(status='SUCCESS',result=operation())
            except Exception as exc:
                logging.getLogger(__name__).exception('Admin operation failed')
                cls.jobs[job_id].update(status='FAILED',error=str(exc))
            finally:cls.jobs[job_id]['completed_at']=iso(utcnow())
        cls.executor.submit(run)
        return dict(cls.jobs[job_id])
