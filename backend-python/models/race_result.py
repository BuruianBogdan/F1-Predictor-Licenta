from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint
from database.db import Base

class RaceResult(Base):
    __tablename__ = 'race_results'
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.driver_id'), nullable=False)
    constructor_id = Column(Integer, ForeignKey('constructors.constructor_id'), nullable=False)
    grid = Column(Integer)
    position = Column(Integer)
    points = Column(Float)
    status = Column(String)
    laps = Column(Integer)
    race_time = Column(String)
    fastest_lap = Column(String)
    source = Column(String, default='manual')
    __table_args__ = (UniqueConstraint('race_id', 'driver_id'),)

    def to_dict(self):
        return {c.name: getattr(self,c.name) for c in self.__table__.columns}
