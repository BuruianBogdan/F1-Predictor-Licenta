"""Bounded, atomic recovery of observations. Never an authenticated/raw feed archive."""
import copy
import gzip
import json
import os
import time
from pathlib import Path
from data_sources.timing_contract import validate_identity


class TimingCheckpointStore:
    max_bytes = 8_000_000
    retention_seconds = 30*86400
    max_sessions = 8

    def __init__(self, directory):
        self.directory = Path(directory)

    def path(self, key):
        return self.directory / (str(int(key))+'-observed-v1.json.gz')

    def save(self, data, diagnostics):
        allowed = ('meta','drivers','events','locations','telemetry','track','public_state',
                   'public_laps','public_pit_entries','public_stint_starts','downloaded_at')
        checkpoint = {'schema_version':1,'saved_at':time.time(),'diagnostics':diagnostics,
                      'data':{k:copy.deepcopy(data[k]) for k in allowed if k in data}}
        if data.get('_ledger'):checkpoint['data']['ledger_fields']=copy.deepcopy(data['_ledger'].fields)
        encoded = json.dumps(checkpoint,separators=(',',':'),allow_nan=False).encode()
        if len(encoded)>self.max_bytes:
            raise ValueError('Timing checkpoint exceeds size limit')
        self.directory.mkdir(parents=True,exist_ok=True)
        target = self.path(data['meta']['session_key']);temporary=target.with_suffix('.tmp')
        with open(temporary,'wb') as output:
            output.write(gzip.compress(encoded));output.flush();os.fsync(output.fileno())
        temporary.replace(target)
        self.prune()

    def load(self, meta):
        target=self.path(meta['session_key'])
        if not target.exists() or time.time()-target.stat().st_mtime>self.retention_seconds:
            return None
        try:
            with gzip.open(target,'rb') as stream:
                raw=stream.read(self.max_bytes+1)
            if len(raw)>self.max_bytes:return None
            checkpoint=json.loads(raw)
            data=checkpoint['data'];saved=data['meta']
            for field in ('session_key','meeting_key','date_start','session_name'):
                if meta.get(field) is not None and saved.get(field)!=meta[field]:return None
            if checkpoint.get('schema_version')!=1:return None
            data.update(complete_archive=False,recovered=True,source='Recovered local observations')
            checkpoint['diagnostics'].update(state='STALE',transport_state='DISCONNECTED',recovered=True,
                error='Recovered checkpoint; no live connection has been started')
            return checkpoint
        except (OSError,ValueError,KeyError,TypeError,RecursionError):
            return None

    def prune(self):
        files=sorted(self.directory.glob('*-observed-v1.json.gz'),key=lambda p:p.stat().st_mtime,reverse=True)
        for index,file in enumerate(files):
            if index>=self.max_sessions or time.time()-file.stat().st_mtime>self.retention_seconds:
                file.unlink(missing_ok=True)
