import math
from collections import defaultdict
from statistics import median

def normalize(rows,driver_ids=None):
    by_provider=defaultdict(dict)
    for row in rows:
        try:driver_id=int(row['driver_id']);odds=float(row.get('decimal_odds',row.get('odds')))
        except (KeyError,TypeError,ValueError) as exc:raise ValueError('Each odds row needs a mapped driver and decimal odds') from exc
        if not math.isfinite(odds) or odds<=1:raise ValueError('Decimal odds must be finite and greater than 1')
        if driver_ids is not None and driver_id not in driver_ids:raise ValueError('Odds driver is not in this race field')
        provider=row.get('provider','manual')
        if driver_id in by_provider[provider]:raise ValueError('Duplicate provider/driver odds')
        by_provider[provider][driver_id]=1/odds
    if not by_provider:return {}
    fair=defaultdict(list)
    for values in by_provider.values():
        total=sum(values.values())
        for driver,p in values.items():fair[driver].append(p/total)
    aggregate={d:median(v) for d,v in fair.items()};total=sum(aggregate.values())
    return {d:p/total for d,p in aggregate.items()}
