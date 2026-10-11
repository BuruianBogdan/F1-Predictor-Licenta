"""Elo rating system for F1 drivers based on race results."""


class EloRating:
    DEFAULT_RATING = 1500.0
    K_FACTOR = 32.0

    def __init__(self, k_factor=None):
        self.k_factor = k_factor or self.K_FACTOR
        self.ratings = {}

    def get(self, driver_id):
        return self.ratings.get(driver_id, self.DEFAULT_RATING)

    def expected_score(self, rating_a, rating_b):
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def update_pair(self, winner_id, loser_id):
        rating_w = self.get(winner_id)
        rating_l = self.get(loser_id)

        expected_w = self.expected_score(rating_w, rating_l)
        expected_l = self.expected_score(rating_l, rating_w)

        self.ratings[winner_id] = rating_w + self.k_factor * (1.0 - expected_w)
        self.ratings[loser_id] = rating_l + self.k_factor * (0.0 - expected_l)

    def update_from_race(self, finished_results):
        """Update ratings from a single race's finished results."""
        sorted_results = sorted(
            [r for r in finished_results if r.position is not None and r.position > 0],
            key=lambda r: r.position,
        )

        for i, winner in enumerate(sorted_results):
            for loser in sorted_results[i + 1:]:
                self.update_pair(winner.driver_id, loser.driver_id)

    def build_from_results(self, results):
        """Process all results chronologically and return driver_id -> rating."""
        by_race = {}
        for result in results:
            by_race.setdefault(result.race_id, []).append(result)

        for race_id in sorted(by_race.keys()):
            self.update_from_race(by_race[race_id])

        return dict(self.ratings)

    def normalize_scores(self, driver_ids):
        """Convert Elo ratings to 0-100 scale for blending with other scores."""
        if not driver_ids:
            return {}

        ratings = {d: self.get(d) for d in driver_ids}
        min_r = min(ratings.values())
        max_r = max(ratings.values())
        span = max_r - min_r

        if span <= 0:
            return {d: 50.0 for d in driver_ids}

        return {
            d: round(((r - min_r) / span) * 100, 2)
            for d, r in ratings.items()
        }
