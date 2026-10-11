"""Rate-limited public OpenF1 archive API. No account or payment is used."""
import time,threading
import requests
from data_sources.base_provider import ProviderError

class RaceControlProvider:
    _lock=threading.RLock();_last_request=0.0
    base='https://api.openf1.org'
    def fetch(self,endpoint,params=None):
        if endpoint not in {'sessions','drivers','laps','location','position','intervals','stints','weather','race_control','session_result','car_data','pit'}:raise ValueError('Unsupported timing endpoint')
        with self._lock:
            time.sleep(max(0,2.1-(time.monotonic()-self.__class__._last_request)))
            self.__class__._last_request=time.monotonic()
            try:
                response=requests.get(self.base+'/v1/'+endpoint,params=params or {},timeout=(6,90))
                if response.status_code in (401,403):raise ProviderError('This session is not public in the archive yet. Try the free live timing feed or wait until it is archived.')
                if response.status_code==429:raise ProviderError('OpenF1 rate limit reached. Wait a minute before trying again.')
                if response.status_code!=200:raise ProviderError(f'OpenF1 {endpoint} is temporarily unavailable (HTTP {response.status_code}).')
                data=response.json()
                if not isinstance(data,list):raise ProviderError('OpenF1 returned an unreadable timing response.')
                return data
            except requests.RequestException:raise ProviderError(f'OpenF1 {endpoint} request failed. Try again shortly.') from None
