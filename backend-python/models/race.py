from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint
from database.db import Base

class Race(Base):
    __tablename__ = 'races'
    race_id = Column(Integer, primary_key=True, autoincrement=True)
    season_year = Column(Integer, nullable=False)
    round = Column(Integer, nullable=False)
    circuit_id = Column(Integer, ForeignKey('circuits.circuit_id'))
    race_name = Column(String)
    date = Column(Date)
    is_completed = Column(Integer, default=0)
    race_status = Column(String, default='SCHEDULED')
    start_at = Column(String)
    weekend_at = Column(String)
    qualifying_at = Column(String)
    sprint_at = Column(String)
    results_verified = Column(Integer, default=0)
    source = Column(String, default='manual')
    __table_args__ = (UniqueConstraint('season_year', 'round'),)

    def to_dict(self):
        return {c.name: (str(getattr(self,c.name)) if c.name == 'date' and self.date else getattr(self,c.name)) for c in self.__table__.columns}
