from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    video_id = Column(String)
    person_id = Column(Integer)
    table_id = Column(Integer)
    event_type = Column(String)
    timestamp = Column(Float)
    embedding = Column(Vector(384))