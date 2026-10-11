import re
from database.db import SessionLocal
from models.analytics import DriverMedia
# Presentation fallbacks only, keyed by constructor identity, never by winner.
TEAM_COLORS={'mercedes':'#27cdb5','ferrari':'#ef3340','mclaren':'#ff8700','red_bull':'#548cff','aston_martin':'#2fc5a5','alpine':'#e797d8','williams':'#4095ef','rb':'#899bff','haas':'#c6c9d2','sauber':'#55df4c','audi':'#ed2839','cadillac':'#c2c2bd'}
class MediaService:
    def get(self,driver_id,constructor_ref=None):
        with SessionLocal() as s:media=s.get(DriverMedia,driver_id)
        color=TEAM_COLORS.get(constructor_ref,'#e54b43')
        if media and re.fullmatch(r'#[0-9a-fA-F]{6}',media.team_color or ''):color=media.team_color
        return {'driver_image':media.image_url if media and media.image_url else '/images/driver-silhouette.svg','team_color':color,'media_source':media.source if media else 'local_fallback'}
