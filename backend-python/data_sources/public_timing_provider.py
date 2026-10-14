"""Public, unauthenticated SignalR timing. Missing channels remain unavailable."""
import copy,json,threading,time,random,logging,math
import requests
from urllib.parse import urlencode
from data_sources.base_provider import ProviderError
from data_sources.timing_contract import FeedHealth,TimingSettings,validate_identity,utc_stamp

def merge_patch(original,patch):
    # SignalR sends sparse object patches for indexed arrays (sectors, stints, messages).
    if isinstance(original,list):original={str(i):value for i,value in enumerate(original)}
    if isinstance(patch,list):patch={str(i):value for i,value in enumerate(patch)}
    if isinstance(patch,dict):
        target=copy.deepcopy(original) if isinstance(original,dict) else {}
        for key,value in patch.items():target[key]=merge_patch(target.get(key),value)
        return target
    return patch

def indexed(value):
    if isinstance(value,list):return value
    if isinstance(value,dict):
        keys=[int(k) for k in value if str(k).isdigit()]
        if not keys or max(keys)>4095:return []
        return [value.get(str(i),value.get(i)) for i in range(max(keys)+1)]
    return []

def seconds(value):
    if isinstance(value,dict):value=value.get('Value')
    if isinstance(value,bool) or value is None or value=='':return None
    try:
        parts=str(value).split(':');total=0
        for part in parts:total=total*60+float(part)
        return total if math.isfinite(total) and 0<=total<=86400 else None
    except (ValueError,TypeError):return None

class PublicTimingFeed:
    url='https://livetiming.formula1.com/signalrcore'
    topics=['SessionInfo','SessionStatus','DriverList','Position.z','CarData.z','TimingData','TimingAppData','TimingStats','RaceControlMessages','WeatherData','TrackStatus','LapCount']
    def __init__(self,session_key,on_patch,on_status,expected=None,health=None):
        self.session_key=session_key;self.on_patch=on_patch;self.on_status=on_status;self.client=None;self.ready=threading.Event();self.accepted=False;self.error=None
        self.expected=expected or {'session_key':session_key};self.health=health or FeedHealth(session_key)
        self.settings=self.health.settings;self.cancel=threading.Event();self.disconnected=threading.Event();self.thread=None;self.last_packet=time.monotonic();self.identity={}
        self.requested=[topic for topic in self.topics if (topic!='Position.z' or self.settings.positions) and (topic!='CarData.z' or self.settings.telemetry)]
        self.health.request(self.requested)
        self.identity_source=None

    def status(self,state,error=None):
        self.health.transport(state,error);self.on_status(state,error)

    def receive(self,topic,patch,date=None):
        source=utc_stamp(date,assume_utc=True) # SignalR feed envelope timestamp is UTC.
        if date is not None and (source is None or source>self.health.clock()):
            self.health.observe(topic,source,valid=False);return
        if isinstance(patch,str) and not topic.endswith('.z'):
            if len(patch)>2_000_000:self.health.observe(topic,None,valid=False);return
            try:patch=json.loads(patch)
            except ValueError:return
        if topic=='SessionInfo':
            if source is not None and self.identity_source is not None and source<self.identity_source:
                self.health.observe(topic,source,valid=False);return
            self.identity=merge_patch(self.identity,patch) if isinstance(patch,dict) else {}
            if source is not None:self.identity_source=source
            self.accepted,self.error=validate_identity(self.identity,self.expected)
            self.health.identity='VERIFIED' if self.accepted else 'REJECTED'
            if not self.accepted:self.status('WAITING',self.error)
        if self.accepted:
            self.last_packet=time.monotonic()
            try:self.on_patch(topic,patch,date)
            except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
                self.health.observe(topic,source,valid=False);return
            if topic=='DriverList':self.ready.set()
            if topic=='SessionInfo' and self.identity.get('SessionStatus')=='Finalised':
                self.status('SESSION_ENDED','The selected session has finalised; use the historical replay')

    def start(self):
        if not self.settings.enabled:raise ProviderError('Public live timing is disabled in configuration')
        if self.thread and self.thread.is_alive():return self
        self.thread=threading.Thread(target=self.supervise,name=f'timing-connection-{self.session_key}',daemon=True)
        self.thread.start();self.ready.wait(15)
        if self.health.state=='ACCESS_DENIED':raise ProviderError('The public source refused access; no credentials or bypass are attempted.')
        return self

    def connect_once(self):
        from signalrcore.hub.base_hub_connection import BaseHubConnection,NegotiationHandler
        import inspect
        # These loggers include negotiated connection IDs at DEBUG. Never enable that output.
        for name in ('SignalRCoreClient','signalrcore'):logging.getLogger(name).setLevel(logging.CRITICAL)
        headers={'User-Agent':'F1-Predictor-ISS/1.0 (local research timing client)'}
        response=requests.options(self.url+'/negotiate',headers=headers,timeout=(5,15))
        if response.status_code in (401,403):
            self.status('ACCESS_DENIED','Public timing access refused (HTTP '+str(response.status_code)+')');return
        # A public load-balancer affinity cookie belongs to ordinary negotiation,
        # not to a browser login or an F1 TV subscription.
        if response.cookies.get('AWSALBCORS'):headers['Cookie']='AWSALBCORS='+response.cookies['AWSALBCORS']
        # Compose the library's handshake/parser/heartbeat with bounded public
        # negotiation. Its default urllib negotiation has no request timeout.
        class BoundedPublicHub(BaseHubConnection):
            def _negotiate(hub):
                response=requests.post(PublicTimingFeed.url+'/negotiate?negotiateVersion=1',headers=hub.headers,
                                       timeout=(5,15),allow_redirects=False)
                response.raise_for_status();payload=response.json()
                if response.status_code!=200 or not isinstance(payload,dict) or payload.get('accessToken') or payload.get('url'):
                    raise ProviderError('Unsupported public negotiation response; authenticated redirects are not followed')
                token=payload.get('connectionToken') or payload.get('connectionId')
                if not isinstance(token,str) or not token:raise ProviderError('Missing public transport connection identifier')
                # connectionToken is a short-lived transport identifier, not an
                # account credential; use it exactly as SignalR Core specifies.
                response_type=inspect.getmodule(NegotiationHandler).NegotiateResponse
                parsed=response_type.from_dict({**payload,'connectionId':token})
                hub.url=PublicTimingFeed.url+'?'+urlencode({'id':token})
                return parsed
        self.client=BoundedPublicHub(self.url,headers=headers,keep_alive_interval=15)
        client=self.client
        def receive(msg):
            if client is not self.client or self.cancel.is_set():return
            if hasattr(msg,'result') and isinstance(msg.result,dict):
                # Identity must be checked before any snapshot topic is accepted.
                if 'SessionInfo' in msg.result:self.receive('SessionInfo',msg.result['SessionInfo'])
                for topic,patch in msg.result.items():
                    if topic!='SessionInfo':self.receive(topic,patch)
            elif isinstance(msg,list) and len(msg)>=2:self.receive(msg[0],msg[1],msg[2] if len(msg)>2 else None)
        def opened():
            if client is not self.client or self.cancel.is_set():return
            self.status('WAITING','Connected; waiting for observations from the selected session')
            client.send('Subscribe',[self.requested],on_invocation=receive)
        def closed():
            if client is self.client:self.disconnected.set()
        client.on_open(opened);client.on('feed',receive);client.on_close(closed)
        client.start()

    def supervise(self):
        began=time.monotonic();attempt=0
        while not self.cancel.is_set() and attempt<self.settings.max_attempts and time.monotonic()-began<self.settings.retry_window:
            attempt+=1;self.health.attempts=attempt;self.accepted=False;self.identity={};self.identity_source=None;self.disconnected.clear();self.last_packet=time.monotonic()
            self.status('CONNECTING' if attempt==1 else 'RECONNECTING')
            try:
                self.connect_once()
                if self.health.state=='ACCESS_DENIED':return
                connected_at=time.monotonic()
                while not self.cancel.wait(1) and not self.disconnected.is_set():
                    if self.health.state=='SESSION_ENDED':return
                    if time.monotonic()-self.last_packet>60:break
                    if time.monotonic()-connected_at>=120 and self.health.snapshot()['state']=='LIVE':
                        # A stable session resets the *failure-window* budget.
                        began=time.monotonic();attempt=0;connected_at=time.monotonic()
            except Exception as exc:
                # Only classify the HTTP status; raw transport exceptions may contain IDs/headers.
                code=getattr(getattr(exc,'response',None),'status_code',None) or getattr(exc,'code',None)
                if code is None and exc.args and exc.args[0] in (401,403):code=exc.args[0]
                if type(exc).__name__=='UnAuthorizedHubError':code=401
                if code in (401,403) or any(s in str(exc) for s in ('401 Unauthorized','403 Forbidden','Status code: 401','Status code: 403')):
                    self.status('ACCESS_DENIED','The upstream refused public access');return
                self.status('RECONNECTING','Public transport interrupted ('+type(exc).__name__+')')
            finally:
                if self.client:
                    try:self.client.stop()
                    except Exception:pass
            if not self.settings.reconnect:break
            delay=min(60,2**(attempt-1))+random.uniform(0,.5)
            if self.cancel.wait(delay):break
        if not self.cancel.is_set():self.status('PROVIDER_UNAVAILABLE','Retry budget exhausted; retry manually when the selected session is broadcasting')

    def stop(self):
        self.cancel.set();self.disconnected.set()
        if self.client:
            try:self.client.stop()
            except Exception:pass
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=2)
        self.status('DISCONNECTED')
