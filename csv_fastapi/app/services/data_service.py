from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "students_complete.csv"


@lru_cache(maxsize=1)
def load_data() -> list[dict]:
    """Load and cache CSV data at startup. Call reload_data() to refresh."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"CSV file not found at: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    # Normalize column names.
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Normalize major casing.
    if "major" in df.columns:
        df["major"] = df["major"].str.strip().str.title()

    # Cast to object first so missing numeric values become real Python None.
    df = df.astype(object).where(pd.notna(df), other=None)

    return df.to_dict(orient="records")


def reload_data():
    """Clear cache and reload CSV from disk."""
    load_data.cache_clear()
    return load_data()


def get_all_students() -> list[dict]:
    return load_data()


def get_student_by_id(student_id: str) -> Optional[dict]:
    data = load_data()
    for row in data:
        if str(row.get("student_id", "")).upper() == student_id.upper():
            return row
    return None


def filter_students(
    major: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    min_gpa: Optional[float] = None,
    max_gpa: Optional[float] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    data = load_data()

    filtered = data

    if major:
        filtered = [r for r in filtered if r.get("major") and major.lower() in r["major"].lower()]
    if city:
        filtered = [r for r in filtered if r.get("city") and city.lower() in r["city"].lower()]
    if status:
        filtered = [r for r in filtered if r.get("status") and status.lower() == str(r["status"]).lower()]
    if min_gpa is not None:
        filtered = [r for r in filtered if r.get("gpa") is not None and r["gpa"] >= min_gpa]
    if max_gpa is not None:
        filtered = [r for r in filtered if r.get("gpa") is not None and r["gpa"] <= max_gpa]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = filtered[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "data": paginated,
    }


def get_summary() -> dict:
    data = load_data()
    gpas = [r["gpa"] for r in data if r.get("gpa") is not None]
    attendances = [r["attendance"] for r in data if r.get("attendance") is not None]

    status_breakdown: dict = {}
    for r in data:
        s = r.get("status") or "Unknown"
        status_breakdown[s] = status_breakdown.get(s, 0) + 1

    return {
        "total": len(data),
        "avg_gpa": round(sum(gpas) / len(gpas), 2) if gpas else None,
        "avg_attendance": round(sum(attendances) / len(attendances), 2) if attendances else None,
        "status_breakdown": status_breakdown,
    }
