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