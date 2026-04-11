-- Coffee Vision bootstrap schema.
-- Run this once on a fresh PostgreSQL database before starting services.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(1024) NOT NULL,
    capture_started_at TIMESTAMP NOT NULL,
    camera_id VARCHAR(32) NOT NULL,
    location_name VARCHAR(128) NOT NULL,
    sector_number INTEGER NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
    total_frames INTEGER NOT NULL DEFAULT 0,
    fps DOUBLE PRECISION NOT NULL DEFAULT 0,
    duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    events_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL,
    table_id INTEGER NULL,
    event_type VARCHAR(64) NOT NULL,
    frame_index INTEGER NOT NULL,
    event_second DOUBLE PRECISION NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    embedding vector(384) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_videos_capture_started_at ON videos (capture_started_at);
CREATE INDEX IF NOT EXISTS idx_videos_camera_id ON videos (camera_id);
CREATE INDEX IF NOT EXISTS idx_events_video_id ON events (video_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_event_timestamp ON events (event_timestamp);
