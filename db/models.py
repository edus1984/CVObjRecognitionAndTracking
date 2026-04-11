from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - fallback for environments without pgvector
    Vector = None


Base = declarative_base()


class EmbeddingType(TypeDecorator):
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if Vector is not None and dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(384))
        return dialect.type_descriptor(String)


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(1024), nullable=False)
    capture_started_at = Column(DateTime, nullable=False)
    camera_id = Column(String(32), nullable=False)
    location_name = Column(String(128), nullable=False)
    sector_number = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_at = Column(DateTime)
    status = Column(String(32), nullable=False, default="uploaded")
    total_frames = Column(Integer, nullable=False, default=0)
    fps = Column(Float, nullable=False, default=0.0)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    events_count = Column(Integer, nullable=False, default=0)

    events = relationship("Event", back_populates="video", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, nullable=False)
    table_id = Column(Integer)
    event_type = Column(String(64), nullable=False, index=True)
    frame_index = Column(Integer, nullable=False)
    event_second = Column(Float, nullable=False)
    event_timestamp = Column(DateTime, nullable=False, index=True)
    embedding = Column(EmbeddingType)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    video = relationship("Video", back_populates="events")