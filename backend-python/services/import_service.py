from services.data_sync_service import F1DataSyncService
class ImportService:
    def import_historical_data(self, start_year, end_year):
        from services.season_service import utcnow
        if not 1950<=start_year<=end_year<=utcnow().year+1: raise ValueError('Invalid season range')
        sync=F1DataSyncService()
        return {'seasons':[sync.sync_season(y) for y in range(start_year,end_year+1)]}
