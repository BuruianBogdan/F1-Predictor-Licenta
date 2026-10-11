"""Compatibility alias: all transport now uses the paginated Jolpica provider."""
from data_sources.jolpica_provider import JolpicaProvider
class ErgastImporter(JolpicaProvider):
    pass
