"""Small, transport-independent contracts for the existing Race Control feed.

Only source observations advance freshness. A socket handshake, a heartbeat and
an undated subscription snapshot are deliberately not timing observations.
"""
import base64
import copy
import hashlib
import json
import math
import os
import threading
import zlib
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta


def utc_stamp(value,assume_utc=False):
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value) if math.isfinite(value) else None
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        # Only provider fields explicitly defined as UTC may omit the suffix.
        # Arbitrary offset-free dates remain invalid.
        if parsed.tzinfo is None and assume_utc:parsed=parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def utc_iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def numeric(value, low, high):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and low <= value <= high else None
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class TimingSettings:
    enabled: bool = True
    diagnostics: bool = True
    persistence: bool = True
    positions: bool = True
    telemetry: bool = True
    projection: bool = True
    reconnect: bool = True
    stale_seconds: float = 20
    max_attempts: int = 6
    retry_window: float = 600
    max_position_samples: int = 1800
    max_car_samples: int = 500
    max_events: int = 4000
    max_laps: int = 200
    multi_provider: bool = True
    openf1_historical: bool = True
    fastf1_historical: bool = True

    @classmethod
    def environment(cls):
        def flag(name, default=True):
            return os.getenv(name, str(default)).lower() in ('true', 'yes', '1')
        stale = numeric(os.getenv('LIVE_STALE_THRESHOLD_SECONDS', '20'), 5, 300)
        if stale is None:raise ValueError('LIVE_STALE_THRESHOLD_SECONDS must be between 5 and 300')
        if os.getenv('LIVE_PRIMARY_PROVIDER','existing_public_timing')!='existing_public_timing':raise ValueError('Unsupported LIVE_PRIMARY_PROVIDER')
        if os.getenv('LIVE_SECONDARY_PROVIDER','none')!='none':raise ValueError('No external secondary live provider has been verified')
        if flag('EXTERNAL_LIVE_ADAPTER_ENABLED',False) or flag('F1TV_AUTOMATION_ENABLED',False):raise ValueError('External live and F1 TV automation are not implemented or enabled')
        if flag('LIVE_SSE_ENABLED',False):raise ValueError('SSE is not enabled; the existing bounded polling transport is used')
        return cls(enabled=flag('LIVE_ENABLED'), diagnostics=flag('LIVE_DIAGNOSTICS_ENABLED'),
                   persistence=flag('LIVE_SNAPSHOT_PERSISTENCE_ENABLED'),
                   positions=flag('LIVE_POSITION_ENABLED'), telemetry=flag('LIVE_TELEMETRY_ENABLED'),
                   projection=flag('LIVE_CHAMPIONSHIP_PROJECTION_ENABLED'), reconnect=flag('LIVE_RECONNECT_ENABLED'),
                   stale_seconds=stale,multi_provider=flag('LIVE_MULTI_PROVIDER_ENABLED'),
                   openf1_historical=flag('OPENF1_HISTORICAL_ENABLED'),fastf1_historical=flag('FASTF1_HISTORICAL_ENABLED'))


CAPABILITIES = {
    'timing': ('TimingData',), 'driver_list': ('DriverList',),
    'sectors': ('TimingData', 'TimingStats'), 'tyres': ('TimingAppData',),
    'race_control': ('RaceControlMessages',), 'weather': ('WeatherData',),
    'positions': ('Position.z',), 'telemetry': ('CarData.z',),
    'lap_count': ('LapCount',), 'track_status': ('TrackStatus',),
}


class FeedHealth:
    def __init__(self, session_key, settings=None, clock=None):
        self.session_key = session_key
        self.settings = settings or TimingSettings.environment()
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self.lock = threading.RLock()
        self.state = 'DISCONNECTED'
        self.error = None
        self.identity = 'UNKNOWN'
        self.attempts = 0
        self.channels = {}
        self.started_at = None
        self.last_transport_at = None
        self.recovered = False

    def request(self, topics):
        with self.lock:
            for topic in topics:
                self.channels.setdefault(topic, {'requested': True, 'packets': 0, 'valid_events': 0,
                    'rejected': 0, 'duplicates': 0, 'last_source_utc': None, 'last_received_utc': None})

    def transport(self, state, error=None):
        with self.lock:
            self.state, self.error = state, error
            self.last_transport_at = self.clock()
            if self.started_at is None:
                self.started_at = self.last_transport_at

    def observe(self, topic, source, received=None, valid=True, duplicate=False):
        with self.lock:
            self.request([topic])
            channel = self.channels[topic]
            channel['packets'] += 1
            channel['last_received_utc'] = utc_iso(received if received is not None else self.clock())
            if duplicate:
                channel['duplicates'] += 1
            elif not valid:
                channel['rejected'] += 1
            else:
                channel['valid_events'] += 1
                previous = utc_stamp(channel['last_source_utc'])
                if source is not None and (previous is None or source > previous):
                    channel['last_source_utc'] = utc_iso(source)
                    channel['last_source_received_utc'] = channel['last_received_utc']

    def snapshot(self, now=None):
        now = self.clock() if now is None else now
        with self.lock:
            channels = copy.deepcopy(self.channels)
            for topic, channel in channels.items():
                source = utc_stamp(channel['last_source_utc'])
                age = max(0, now-source) if source is not None else None
                channel['age_seconds'] = age
                channel['state'] = ('UNAUTHORIZED' if self.state == 'ACCESS_DENIED' else
                    'STALE' if self.recovered or self.identity=='REJECTED' or age is not None and age > self.settings.stale_seconds else
                    'AVAILABLE' if age is not None else 'PARTIAL' if channel['valid_events'] else 'MISSING')
                channel['latency_seconds'] = (utc_stamp(channel.get('last_source_received_utc'))-source
                    if source is not None and channel.get('last_source_received_utc') else None)
                channel['explanation'] = ('Subscribed, but no observations received' if not channel['packets'] else
                    'Snapshot has no verified source timestamp' if source is None else
                    'Source observations stopped advancing' if channel['state'] == 'STALE' else None)
            timing = channels.get('TimingData', {})
            state = self.state
            if self.recovered and state not in ('ACCESS_DENIED','SESSION_ENDED','PROVIDER_UNAVAILABLE'):
                state = 'STALE'
            elif state in ('WAITING', 'CONNECTED', 'LIVE', 'STALE'):
                state = ('LIVE' if self.identity == 'VERIFIED' and timing.get('state') == 'AVAILABLE' else
                         'STALE' if timing.get('state') == 'STALE' else 'WAITING')
            capabilities = {}
            for name, topics in CAPABILITIES.items():
                values = [channels.get(topic, {}).get('state', 'MISSING') for topic in topics]
                capabilities[name] = ('UNSUPPORTED' if name == 'positions' and not self.settings.positions or
                                      name == 'telemetry' and not self.settings.telemetry else
                                      'AVAILABLE' if all(s == 'AVAILABLE' for s in values) else
                                      'PARTIAL' if any(s in ('AVAILABLE', 'PARTIAL') for s in values) else
                                      'UNAUTHORIZED' if 'UNAUTHORIZED' in values else 'STALE' if 'STALE' in values else 'MISSING')
            return {'schema_version': 1, 'provider_id': 'existing_public_timing',
                    'session_key': self.session_key, 'state': state, 'transport_state': self.state,
                    'identity': self.identity, 'error': self.error, 'attempts': self.attempts,
                    'last_transport_utc': utc_iso(self.last_transport_at), 'recovered': self.recovered,
                    'channels': channels, 'capabilities': capabilities, 'cutoff_utc': utc_iso(now),
                    'last_valid_observation_utc':max((c['last_source_utc'] for c in channels.values() if c['last_source_utc']),default=None),
                    'last_received_packet_utc':max((c['last_received_utc'] for c in channels.values() if c['last_received_utc']),default=None),
                    'data_age_seconds':timing.get('age_seconds'),
                    'latency_seconds':timing.get('latency_seconds')}


def validate_identity(info, expected):
    """Check the full meeting context when provided; never guess from car numbers."""
    if not isinstance(info, dict):
        return False, 'Malformed session identity'
    try:
        if int(info.get('Key', -1)) != int(expected['session_key']):
            return False, 'The public feed belongs to another session'
        if expected.get('meeting_key') is not None and int(info.get('Meeting', {}).get('Key', -1)) != int(expected['meeting_key']):
            return False, 'Meeting identity does not match the selected race'
    except (ValueError, TypeError):
        return False, 'Malformed session or meeting key'
    if expected.get('session_name') and info.get('Name') != expected['session_name']:
        aliases = {'Sprint Shootout', 'Sprint Qualifying'}
        if not {info.get('Name'), expected['session_name']} <= aliases:
            return False, 'Session type/name does not match'
    if expected.get('session_type') and info.get('Type') != expected['session_type']:
        return False, 'Session type does not match'
    start = expected.get('date_start')
    if start:
        try:
            local = datetime.fromisoformat(info['StartDate'])
            if not local.tzinfo:
                offset = str(info['GmtOffset'])
                sign = -1 if offset.startswith('-') else 1
                parts = [int(p) for p in offset.lstrip('+-').split(':')]
                seconds_offset = sign * (parts[0]*3600 + parts[1]*60 + (parts[2] if len(parts)>2 else 0))
                local = local.replace(tzinfo=timezone(timedelta(seconds=seconds_offset)))
            selected = utc_stamp(start)
            if selected is None or abs(local.timestamp()-selected) > 1800:
                return False, 'Session start time does not match the calendar'
            path_year = str(info.get('Path', '')).split('/')[0]
            if path_year and path_year != str(datetime.fromtimestamp(selected, timezone.utc).year):
                return False, 'Season identity does not match'
        except (KeyError, ValueError, TypeError, IndexError):
            return False, 'Incomplete session start/UTC-offset identity'
    return True, None


class PatchLedger:
    """Timestamped leaf merge: an older packet can add a missing leaf, never replace a newer one."""
    def __init__(self, session_key, max_ids=4096):
        self.session_key = session_key
        self.fields = {}
        self.ids = set()
        self.order = deque(maxlen=max_ids)

    def apply(self, topic, original, patch, source, received):
        def check_shape(value,depth=0):
            if depth>32:raise ValueError('Timing patch nesting exceeds limit')
            if isinstance(value,dict):
                if len(value)>4000:raise ValueError('Timing object exceeds entry limit')
                for v in value.values():check_shape(v,depth+1)
            elif isinstance(value,list):
                if len(value)>4000:raise ValueError('Timing array exceeds entry limit')
                for v in value:check_shape(v,depth+1)
            elif isinstance(value,float) and not math.isfinite(value):raise ValueError('Non-finite timing number')
        check_shape(patch)
        if len(self.fields)>60000:raise ValueError('Timing session field limit exceeded')
        digest = hashlib.sha256(json.dumps([self.session_key, topic, source, patch],
                         sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if digest in self.ids:
            return copy.deepcopy(original), False, True
        if len(self.order) == self.order.maxlen:
            self.ids.discard(self.order[0])
        self.order.append(digest); self.ids.add(digest)
        changed = False
        def merge(old, new, path):
            nonlocal changed
            if isinstance(new, list):
                new = {str(i):v for i,v in enumerate(new)}
            if isinstance(old, list):
                old = {str(i):v for i,v in enumerate(old)}
            if isinstance(new, dict):
                deleted_at=self.fields.get(path,{}).get('source_timestamp')
                if old is None and deleted_at is not None and (source is None or source<deleted_at):return None
                target = copy.deepcopy(old) if isinstance(old, dict) else {}
                # Explicit tombstones remove indexed entries. Null is an explicit value.
                if new.get('_deleted') is True:
                    return merge(old, None, path)
                deleted=new.get('_deleted')
                if isinstance(deleted,list):
                    for key in deleted:
                        target[str(key)]=merge(target.get(str(key)),None,path+'.'+str(key))
                for key, value in new.items():
                    if key=='_deleted':continue
                    target[str(key)] = merge(target.get(str(key)), value, path+'.'+str(key))
                return target
            parts=path.split('.')
            parents=[self.fields[key] for key in ('.'.join(parts[:i]) for i in range(1,len(parts))) if key in self.fields]
            if new is None:parents.extend(p for key,p in self.fields.items() if key.startswith(path+'.'))
            previous = self.fields.get(path)
            newer=[p for p in parents if p.get('source_timestamp') is not None]
            if newer:
                latest=max(newer,key=lambda p:p['source_timestamp'])
                if previous is None or previous.get('source_timestamp') is None or latest['source_timestamp']>previous['source_timestamp']:previous=latest
            previous_source = previous.get('source_timestamp') if previous else None
            if previous and (source is None and previous_source is not None or
                             source is not None and previous_source is not None and source < previous_source):
                return copy.deepcopy(old)
            changed = True
            self.fields[path] = {'provider_id': 'existing_public_timing', 'session_key': self.session_key,
                'source_timestamp': source, 'observed_utc': utc_iso(source), 'received_utc': utc_iso(received),
                'validity': 'OBSERVED' if source is not None else 'UNDATED_SNAPSHOT'}
            return copy.deepcopy(new)
        return merge(original, patch, topic), changed, False

    def provenance(self, path, at):
        item = copy.deepcopy(self.fields.get(path))
        if item:
            source = item.pop('source_timestamp', None)
            item['age_seconds'] = max(0, at-source) if source is not None else None
        return item


def decode_channel(encoded, max_encoded=2_000_000, max_decoded=8_000_000):
    """Bounded base64 + raw-deflate/zlib decoding; refuses bombs and trailing streams."""
    if not isinstance(encoded, str) or len(encoded) > max_encoded:
        raise ValueError('Compressed channel exceeds encoded size limit')
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid base64 channel') from exc
    decoded = None
    for bits in (-zlib.MAX_WBITS, zlib.MAX_WBITS):
        try:
            decoder = zlib.decompressobj(bits)
            value = decoder.decompress(compressed, max_decoded+1)
            if len(value) > max_decoded or decoder.unconsumed_tail:
                raise ValueError('Compressed channel exceeds decoded size limit')
            if not decoder.eof or decoder.unused_data:
                raise ValueError('Incomplete or trailing compressed stream')
            decoded = value; break
        except zlib.error:
            continue
    if decoded is None:
        raise ValueError('Invalid compressed channel')
    try:
        result = json.loads(decoded)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid compressed JSON') from exc
    if not isinstance(result, dict):
        raise ValueError('Compressed channel must contain an object')
    return result
