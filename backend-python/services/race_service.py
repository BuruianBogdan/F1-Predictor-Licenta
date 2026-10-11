from repositories.race_repository import RaceRepository


class RaceService:

    def __init__(self):
        self.repo = RaceRepository()

    def get_races(self):
        races = self.repo.get_all_races()
        return [race.to_dict() for race in races]

    def get_race(self, race_id):
        race = self.repo.get_race(race_id)
        if race:
            return race.to_dict()
        return None

    def create_race(self, race_data):
        race = self.repo.add_race(race_data)
        return race.to_dict()

    def update_race(self, race_id, race_data):
        race = self.repo.update_race(race_id, race_data)
        if race:
            return race.to_dict()
        return None

    def remove_race(self, race_id):
        self.repo.delete_race(race_id)