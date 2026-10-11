"""Public, unauthenticated SignalR timing. Missing channels remain unavailable."""
import copy,json,threading
import requests
from data_sources.base_provider import ProviderError

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
    if isinstance(value,dict):return [v for k,v in sorted(value.items(),key=lambda pair:int(pair[0]) if str(pair[0]).isdigit() else -1) if str(k).isdigit()]
    return []

def seconds(value):
    if isinstance(value,dict):value=value.get('Value')
    if not value:return None
    try:
        parts=str(value).split(':');total=0
        for part in parts:total=total*60+float(part)
        return total
    except ValueError:return None

class PublicTimingFeed:
    url='https://livetiming.formula1.com/signalrcore'
    topics=['SessionInfo','SessionStatus','DriverList','Position.z','CarData.z','TimingData','TimingAppData','TimingStats','RaceControlMessages','WeatherData','TrackStatus','LapCount']
    def __init__(self,session_key,on_patch,on_status):
        self.session_key=session_key;self.on_patch=on_patch;self.on_status=on_status;self.client=None;self.ready=threading.Event();self.accepted=False;self.error=None

    def receive(self,topic,patch,date=None):
        if isinstance(patch,str) and not topic.endswith('.z'):
            try:patch=json.loads(patch)
            except ValueError:return
        if topic=='SessionInfo':
            key=patch.get('Key') if isinstance(patch,dict) else None
            if key is not None:
                self.accepted=int(key)==self.session_key
                if not self.accepted:self.error='The public feed is still on another session. Try again when the selected session starts.';self.on_status('WAITING',self.error)
        if self.accepted:
            self.on_patch(topic,patch,date)
            if topic=='DriverList':self.ready.set()

    def start(self):
        from signalrcore.hub_connection_builder import HubConnectionBuilder
        headers={}
        response=requests.options(self.url+'/negotiate',timeout=(5,15))
        if response.status_code>=400:raise ProviderError('Public timing is unavailable; historical replay remains available.')
        if response.cookies.get('AWSALBCORS'):headers['Cookie']='AWSALBCORS='+response.cookies['AWSALBCORS']
        self.client=HubConnectionBuilder().with_url(self.url,options={'verify_ssl':True,'headers':headers}).with_automatic_reconnect({'type':'raw','keep_alive_interval':15,'reconnect_interval':5,'max_attempts':5}).build()
        def receive(msg):
            if hasattr(msg,'result') and isinstance(msg.result,dict):
                # Identity must be checked before any snapshot topic is accepted.
                if 'SessionInfo' in msg.result:self.receive('SessionInfo',msg.result['SessionInfo'])
                for topic,patch in msg.result.items():
                    if topic!='SessionInfo':self.receive(topic,patch)
            elif isinstance(msg,list) and len(msg)>=2:self.receive(msg[0],msg[1],msg[2] if len(msg)>2 else None)
        def opened():
            self.on_status('CONNECTED',None)
            self.client.send('Subscribe',[self.topics],on_invocation=receive)
        self.client.on_open(opened);self.client.on('feed',receive);self.client.on_close(lambda:self.on_status('RECONNECTING','Public feed interrupted; reconnecting.'))
        try:
            self.client.start()
            if not self.ready.wait(15):raise ProviderError(self.error or 'No public timing is being transmitted yet. Try again during the session.')
            return self
        except Exception:
            self.stop();raise

    def stop(self):
        if self.client:self.client.stop()
