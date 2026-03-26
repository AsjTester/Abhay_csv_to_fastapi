from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.models.student import Student, StudentSummary
from app.services import data_service
from app.web import build_url, templates, wants_html

router = APIRouter(prefix="/data", tags=["Students"])


def build_filter_params(
    major: str | None,
    city: str | None,
    status: str | None,
    min_gpa: float | None,
    max_gpa: float | None,
    page: int,
    page_size: int,
) -> dict:
    return {
        "major": major,
        "city": city,
        "status": status,
        "min_gpa": min_gpa,
        "max_gpa": max_gpa,
        "page": page,
        "page_size": page_size,
    }


@router.get("/", summary="Get all students (paginated + filterable)")
def get_all_students(
    request: Request,
    major: str | None = Query(None, description="Filter by major (partial match)"),
    city: str | None = Query(None, description="Filter by city (partial match)"),
    status: str | None = Query(None, description="Filter by status: Paid | Pending | Overdue"),
    min_gpa: float | None = Query(None, ge=0.0, le=4.0, description="Minimum GPA"),
    max_gpa: float | None = Query(None, ge=0.0, le=4.0, description="Maximum GPA"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Records per page"),
):
    result = data_service.filter_students(
        major=major,
        city=city,
        status=status,
        min_gpa=min_gpa,
        max_gpa=max_gpa,
        page=page,
        page_size=page_size,
    )

    if wants_html(request):
        filters = build_filter_params(major, city, status, min_gpa, max_gpa, page, page_size)
        prev_url = None
        next_url = None
        if result["page"] > 1:
            prev_url = build_url(request.url.path, {**filters, "page": result["page"] - 1})
        if result["page"] < result["total_pages"]:
            next_url = build_url(request.url.path, {**filters, "page": result["page"] + 1})

        return templates.TemplateResponse(
            request=request,
            name="students.html",
            context={
                "result": result,
                "students": result["data"],
                "filters": filters,
                "json_url": build_url(request.url.path, {**filters, "format": "json"}),
                "prev_url": prev_url,
                "next_url": next_url,
            },
        )

    return result


@router.get("/summary", response_model=StudentSummary, summary="Get dataset summary statistics")
def get_summary(request: Request):
    summary = data_service.get_summary()

    if wants_html(request):
        preview = data_service.filter_students(page=1, page_size=5)["data"]
        return templates.TemplateResponse(
            request=request,
            name="summary.html",
            context={
                "summary": summary,
                "preview": preview,
                "json_url": build_url(request.url.path, {"format": "json"}),
            },
        )

    return summary


@router.get("/reload", summary="Reload CSV data page", response_class=HTMLResponse)
def reload_page(request: Request):
    summary = data_service.get_summary()
    return templates.TemplateResponse(
        request=request,
        name="reload.html",
        context={
            "message": None,
            "total_records": summary["total"],
            "status_breakdown": summary["status_breakdown"],
        },
    )


@router.post("/reload", summary="Reload CSV data from disk")
def reload_data(request: Request):
    data = data_service.reload_data()
    payload = {"message": "Data reloaded successfully.", "total_records": len(data)}

    if wants_html(request):
        summary = data_service.get_summary()
        return templates.TemplateResponse(
            request=request,
            name="reload.html",
            context={
                **payload,
                "status_breakdown": summary["status_breakdown"],
            },
        )

    return payload


@router.get("/{student_id}", response_model=Student, summary="Get student by ID")
def get_student(request: Request, student_id: str):
    student = data_service.get_student_by_id(student_id)
    if not student:
        if wants_html(request):
            return templates.TemplateResponse(
                request=request,
                name="student_detail.html",
                context={
                    "student": None,
                    "student_id": student_id,
                    "json_url": build_url(request.url.path, {"format": "json"}),
                },
                status_code=404,
            )
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")

    if wants_html(request):
        return templates.TemplateResponse(
            request=request,
            name="student_detail.html",
            context={
                "student": student,
                "student_id": student_id,
                "json_url": build_url(request.url.path, {"format": "json"}),
            },
        )

    return student
