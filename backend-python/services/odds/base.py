from abc import ABC, abstractmethod
class OddsProvider(ABC):
    name='abstract'
    def provider_name(self):return self.name
    def is_available(self):return True
    def health_check(self):return {'provider':self.name,'available':self.is_available()}
    @abstractmethod
    def fetch_race_odds(self,race): ...
