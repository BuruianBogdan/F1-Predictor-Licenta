import json
import _bootstrap
from services.data_quality_service import DataQualityService
if __name__ == '__main__': print(json.dumps(DataQualityService().report(),indent=2))
