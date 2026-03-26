from pydantic import BaseModel, field_validator
from typing import Optional


class Student(BaseModel):
    student_id: str
    first_name: str
    last_name: str
    age: Optional[int] = None
    major: Optional[str] = None
    gpa: Optional[float] = None
    attendance: Optional[float] = None
    scholarship: Optional[float] = None
    city: Optional[str] = None
    status: Optional[str] = None

    @field_validator("major", mode="before")
    @classmethod
    def normalize_major(cls, v):
        if v and isinstance(v, str):
            return v.strip().title()
        return v


class StudentSummary(BaseModel):
    total: int
    avg_gpa: Optional[float]
    avg_attendance: Optional[float]
    status_breakdown: dict
