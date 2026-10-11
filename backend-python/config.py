"""Configuration resolved once without network side effects; the app starts news scheduling explicitly."""
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / '.env')
DATA_DIR = Path(os.getenv('F1_DATA_DIR', str(BACKEND_DIR / 'data'))).resolve()
DB_PATH = BASE_DIR / 'database' / 'f1.db'
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DB_PATH}')
def flag(name, default='false'):
    return os.getenv(name, default).lower() in ('1', 'true', 'yes')
DEBUG = flag('FLASK_DEBUG')
HOST = os.getenv('FLASK_HOST', '127.0.0.1')
PORT = int(os.getenv('FLASK_PORT', '5000'))
JOLPICA_BASE_URL = os.getenv('JOLPICA_BASE_URL', os.getenv('ERGAST_BASE_URL', 'https://api.jolpi.ca/ergast/f1')).rstrip('/')
HTTP_TIMEOUT = int(os.getenv('HTTP_TIMEOUT_SECONDS', '25'))
FASTF1_CACHE_DIR = Path(os.getenv('FASTF1_CACHE_DIR', str(DATA_DIR / 'cache/fastf1')))
MODEL_DIR = DATA_DIR / 'models'
PREDICTION_MODE = os.getenv('PREDICTION_MODE', 'ml').lower()
MARKET_ENABLED = flag('MARKET_ENABLED', 'true')
MARKET_ODDS_WEIGHT = float(os.getenv('MARKET_WEIGHT', os.getenv('MARKET_ODDS_WEIGHT', '0.15')))
if not 0 <= MARKET_ODDS_WEIGHT <= 1:
    raise ValueError('MARKET_WEIGHT must be between 0 and 1')
MARKET_MODEL_WEIGHT = 1 - MARKET_ODDS_WEIGHT
USE_SELENIUM_ODDS = flag('SELENIUM_ENABLED', os.getenv('USE_SELENIUM_ODDS', 'false'))
CHAMPIONSHIP_SIMULATIONS = int(os.getenv('CHAMPIONSHIP_SIMULATIONS', '5000'))
RANDOM_SEED = int(os.getenv('RANDOM_SEED', '42'))
LLM_ENABLED = flag('LLM_ENABLED')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', '')
# Compatibility for legacy callers; never a fixed current year.
ERGAST_BASE_URL, ERGAST_TIMEOUT = JOLPICA_BASE_URL, HTTP_TIMEOUT
LIVE_REFRESH_YEAR = datetime.now(timezone.utc).year
USE_FASTF1_REFRESH = flag('USE_FASTF1_REFRESH')
