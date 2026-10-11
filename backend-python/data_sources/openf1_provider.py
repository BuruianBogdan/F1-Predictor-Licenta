"""Optional media enrichment from historical sessions, never required to boot."""
import requests
from config import HTTP_TIMEOUT
from data_sources.base_provider import ProviderError
class OpenF1Provider:
    name='openf1'
    def fetch_drivers(self, session_key):
        try:
            r=requests.get('https://api.openf1.org/v1/drivers',params={'session_key':int(session_key)},headers={'User-Agent':'F1Predictor/2.0'},timeout=HTTP_TIMEOUT)
            r.raise_for_status();data=r.json()
            if not isinstance(data,list):raise ValueError('Expected a driver list')
            return data
        except (requests.RequestException,ValueError) as exc:
            raise ProviderError('OpenF1 media unavailable; local silhouette remains available') from exc
