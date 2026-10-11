from sqlalchemy import func
from database.db import SessionLocal
from models.race_result import RaceResult
from models.driver import Driver
from models.constructor import Constructor


class StandingsRepository:

    def get_driver_standings(self):
        session = SessionLocal()

        rows = (
            session.query(
                Driver.driver_id,
                Driver.forename,
                Driver.surname,
                Driver.code,
                func.sum(RaceResult.points).label("total_points")
            )
            .join(RaceResult, Driver.driver_id == RaceResult.driver_id)
            .group_by(Driver.driver_id, Driver.forename, Driver.surname, Driver.code)
            .order_by(func.sum(RaceResult.points).desc())
            .all()
        )

        session.close()
        return rows

    def get_constructor_standings(self):
        session = SessionLocal()

        rows = (
            session.query(
                Constructor.constructor_id,
                Constructor.name,
                Constructor.nationality,
                func.sum(RaceResult.points).label("total_points")
            )
            .join(RaceResult, Constructor.constructor_id == RaceResult.constructor_id)
            .group_by(Constructor.constructor_id, Constructor.name, Constructor.nationality)
            .order_by(func.sum(RaceResult.points).desc())
            .all()
        )

        session.close()
        return rows