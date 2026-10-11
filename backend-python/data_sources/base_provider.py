from abc import ABC, abstractmethod

class ProviderError(RuntimeError):
    pass

class F1Provider(ABC):
    name = 'abstract'
    @abstractmethod
    def fetch_races(self, season): ...
    @abstractmethod
    def fetch_results(self, season): ...
