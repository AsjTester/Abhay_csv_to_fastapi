# 🎓 Student Data API

A **FastAPI** service that loads student records from a CSV file into memory at startup and exposes clean, documented REST endpoints for fetching, filtering, and summarizing the data.

---

## 📁 Project Structure

```
student_api/
├── main.py                  # FastAPI app entry point
├── requirements.txt
├── data/
│   └── students_complete.csv
└── app/
    ├── models/
    │   └── student.py       # Pydantic response models
    ├── routers/
    │   └── students.py      # Route definitions
    └── services/
        └── data_service.py  # CSV loading, caching, filtering logic
```

---

## ⚙️ Setup & Run

### 1. Clone / navigate to the project
```bash
cd student_api
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the server
```bash
uvicorn main:app --reload
```

The API will be live at: **http://127.0.0.1:8000**

---

## 📖 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Health check (JSON) |
| `GET` | `/data/` | All students (filterable + paginated) |
| `GET` | `/data/summary` | Aggregate stats |
| `GET` | `/data/{student_id}` | Single student by ID |
| `POST` | `/data/reload` | Reload CSV from disk |

### 🔍 Filter & Pagination Query Params (`GET /data/`)

| Param | Type | Description |
|-------|------|-------------|
| `major` | string | Partial match on major (e.g. `science`) |
| `city` | string | Partial match on city (e.g. `seattle`) |
| `status` | string | Exact match: `Paid`, `Pending`, `Overdue` |
| `min_gpa` | float | Minimum GPA (0.0–4.0) |
| `max_gpa` | float | Maximum GPA (0.0–4.0) |
| `page` | int | Page number (default: 1) |
| `page_size` | int | Records per page (default: 20, max: 100) |

---

## 🧪 Example Requests

```bash
# All students
curl http://127.0.0.1:8000/data/

# Filter by major and minimum GPA
curl "http://127.0.0.1:8000/data/?major=data+science&min_gpa=3.0"

# Filter by city and status
curl "http://127.0.0.1:8000/data/?city=seattle&status=Paid"

# Get specific student
curl http://127.0.0.1:8000/data/STU_1000

# Dataset summary
curl http://127.0.0.1:8000/data/summary

# Reload CSV after editing
curl -X POST http://127.0.0.1:8000/data/reload
```

---

## ✅ Interactive Docs

FastAPI auto-generates Swagger UI at:
- **Swagger:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

---

## 🧠 Design Decisions

- **CSV loaded once at startup** using `functools.lru_cache` — no re-reading on every request.
- **`/data/reload`** endpoint lets you refresh in-memory data without restarting the server.
- **Pydantic models** validate and serialize all responses cleanly.
- **Edge cases handled**: missing GPA values, mixed-case majors, case-insensitive ID lookups.
- Filtering is done **in-memory** (no DB), suitable for datasets up to ~100k rows.

---

## 👥 Team

**Project-K** | Team Members: Abhay Shankar Jaiswal 
