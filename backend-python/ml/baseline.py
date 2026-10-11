"""Named weighted baseline: no target-race outcome terms."""
import numpy as np
from scipy.special import softmax

class HeuristicBaselineModel:
    version='heuristic-baseline-v2'
    def predict(self, rows):
        f=[r['features'] for r in rows]
        scores=np.array([-(x['avg_finish_last_5']*.5+x['constructor_avg_finish_last_5']*.3+x['driver_circuit_avg_finish']*.2)/2 + x['finish_rate_last_10']*.3 + (-(x['qualifying_position']-10)*.10 if x['qualifying_known'] else 0) for x in f])
        win=softmax(scores)
        # Plackett-Luce ranking distribution, deterministic Monte Carlo marginals.
        rng=np.random.default_rng(42)
        order=np.argsort(-(np.log(win)[None,:]+rng.gumbel(size=(3000,len(win)))),axis=1)
        rank=np.argsort(order,axis=1)
        return {'win':win,'podium':(rank<3).mean(axis=0),'points':(rank<10).mean(axis=0),'score':win}
