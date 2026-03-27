# Student Data API

A FastAPI service that imports student records from a CSV file into a MySQL table on localhost and then serves filtering, detail, and summary endpoints from MySQL.

## Project Structure

```text
csv_fastapi/
|-- main.py
|-- requirements.txt
|-- data/
|   `-- students_complete.csv
`-- app/
    |-- models/
    |   `-- student.py
    |-- routers/
    |   `-- students.py
    `-- services/
        `-- data_service.py
```

## What Changed

- On startup, the app connects to MySQL and creates the database if it does not already exist.
- It creates a table named from the CSV filename stem.
  Example: `students_complete.csv` becomes table `students_complete`.
- `POST /data/reload` re-imports the CSV into MySQL.
- All student list, detail, filter, and summary endpoints now read from MySQL instead of an in-memory cache.

## Prerequisites

- Python 3.11+
- MySQL running on `localhost:3306`
- A MySQL user that can create databases and tables

## Setup

### 1. Create and activate a virtual environment

```powershell
python -m venv csvreader
.\csvreader\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure MySQL connection settings

PowerShell example:

```powershell
$env:MYSQL_HOST='localhost'
$env:MYSQL_PORT='3306'
$env:MYSQL_USER='root'
$env:MYSQL_PASSWORD='your_password'
$env:MYSQL_DATABASE='csv_fastapi'
```

Optional CSV override:

```powershell
$env:CSV_FILE_PATH='data/students_complete.csv'
```

If you point `CSV_FILE_PATH` to `data/student.csv`, the app will create and use table `student`.

### 4. Run the API

```powershell
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | HTML homepage |
| `GET` | `/health` | Health details including configured database/table |
| `GET` | `/data/` | All students (filterable + paginated) |
| `GET` | `/data/summary` | Aggregate stats from MySQL |
| `GET` | `/data/{student_id}` | Single student by ID |
| `GET` | `/data/reload` | HTML sync page |
| `POST` | `/data/reload` | Re-import CSV into MySQL |

## Example Requests

```powershell
curl http://127.0.0.1:8000/data/
curl "http://127.0.0.1:8000/data/?major=data+science&min_gpa=3.0"
curl http://127.0.0.1:8000/data/STU_1000
curl http://127.0.0.1:8000/data/summary
curl -X POST http://127.0.0.1:8000/data/reload
```

## Notes

- The app auto-creates the configured MySQL database if permissions allow it.
- The table name always comes from the CSV filename.
- The import step clears the destination table and loads the latest CSV contents.
- If MySQL is unavailable, the homepage and reload page show the connection error so you can fix the local configuration.
