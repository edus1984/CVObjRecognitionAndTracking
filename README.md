## ☕ Coffee Vision POC

Coffee Vision is a Proof‑of‑Concept for analyzing café operations using Computer Vision and AI. The system processes uploaded videos, detects customers and waiters, extracts events, calculates KPIs, and enables natural language queries using RAG.

---

## 🎯 Features (Current POC)

* Upload videos manually
* Detect people using YOLO
* Track individuals using ByteTrack
* Generate operational events
* Store results in PostgreSQL
* Store embeddings using PGVector
* Query insights using RAG
* Simple dashboard with KPIs

---

## 🧱 Architecture

```
Streamlit Dashboard
        ↓
FastAPI Backend
        ↓
Vision Pipeline (YOLO + ByteTrack)
        ↓
Event Engine
        ↓
PostgreSQL + PGVector
        ↓
RAG (LangChain + HuggingFace)
```

---

## 🛠 Tech Stack

### Backend

* Python
* FastAPI

### Vision

* YOLO (Ultralytics)
* ByteTrack
* OpenCV
* Supervision

### Database

* PostgreSQL
* PGVector

### RAG

* LangChain
* HuggingFace SentenceTransformers

### Dashboard

* Streamlit

---

## 🚀 Quick Start

### 1. Install dependencies

```
pip install -r requirements.txt
```

### 2. Create database

```
CREATE DATABASE coffeevision;
CREATE EXTENSION vector;
```

### 3. Start API

```
uvicorn api.main:app --reload
```

### 4. Start dashboard

```
streamlit run dashboard/app.py
```

---

## 📊 Example KPIs

* Customers per hour
* Average service time
* Table occupancy
* Wait time
* Customer duration

---

## 📁 Project Structure

```
coffee-vision/
│
├── api/
│   └── main.py
│
├── vision/
│   ├── detector.py
│   ├── tracker.py
│   ├── events.py
│   └── pipeline.py
│
├── db/
│   ├── database.py
│   ├── models.py
│   └── queries.py
│
├── rag/
│   ├── embeddings.py
│   ├── retriever.py
│   └── qa.py
│
├── dashboard/
│   └── app.py
│
├── videos/
├── requirements.txt
└── config.py
```

---

## 🧠 Future Improvements

* Multi-camera support
* Real-time processing
* Waiter detection
* Table detection
* Better event detection

---

## 🆕 New Features Added

### 1. Database bootstrap SQL (first run)

The project now includes a bootstrap script at `db/init_schema.sql`.

Run it once after creating your PostgreSQL database:

```sql
\i db/init_schema.sql
```

It creates:

* `videos` table with capture metadata and processing status
* `events` table with foreign key to `videos(id)`
* indexes for capture/event timestamps, camera ID, and event type

### 2. Video filename validation and metadata parsing

Uploads are now validated against this format:

```text
[datetime]_[cameraID]_[location][sector].[ext]
```

Example:

```text
20260324T150520_C0104_SouthEast28.mp4
```

Parsed fields:

* capture start datetime (`2026-03-24 15:05:20`)
* camera ID (`C0104`)
* location name (`SouthEast`)
* sector number (`28`)
* extension (`mp4`, `dav`, etc.)

Invalid names are rejected with `HTTP 400`.

### 3. Video/event persistence in processing pipeline

When a video is uploaded:

1. A `videos` row is created.
2. `process_video` runs detection/tracking/event extraction.
3. Events are stored in `events` linked with `video_id`.
4. Video status is updated (`uploaded -> processing -> completed/failed`).

Timing model:

* `event_second` = relative seconds within video
* `event_timestamp` = `capture_started_at + event_second`

### 4. New API endpoint

* `POST /upload`: validates filename, persists metadata, processes video, stores events.
* `GET /videos`: returns uploaded videos with pagination and filters.
* `GET /kpis`: returns live dashboard KPI aggregates from database.

`GET /videos` query params:

* `skip` (default `0`)
* `limit` (default `20`, max `100`)
* `camera_id` (optional)
* `status` (optional)
* `capture_from` (optional ISO datetime)
* `capture_to` (optional ISO datetime)

Response shape:

* `items`: video rows
* `pagination`: `skip`, `limit`, `returned`, `total`

### 5. Dashboard right column (20%)

The dashboard now uses an 80/20 layout:

* Left 80%: upload + KPI area
* Right 20%:
        * top: video visualizer
        * bottom: list of uploaded videos with status and event counts

Dashboard now pulls live KPI values from `GET /kpis` and video list data from paginated `GET /videos`.

### 6. Verbose processing logs

Added logging for:

* upload validation and rejection reasons
* processing start/end
* frame progress checkpoints
* event persistence summary
* processing failure path

### 7. FastAPI startup modernization

Startup initialization was migrated from deprecated startup events to FastAPI lifespan handlers.

### 8. Test suite updates

New tests were added under `tests/`:

* Unit tests:
  * filename parser validation
  * event engine behavior
* Integration-style tests (mock-heavy):
  * upload endpoint behavior
        * list videos filters + pagination
        * KPI endpoint aggregates
  * pipeline persistence flow
* Dashboard behavior tests:
        * upload helper success path
        * uploaded-videos fetch failure fallback
        * KPI fallback handling

Run tests:

```bash
pytest
```