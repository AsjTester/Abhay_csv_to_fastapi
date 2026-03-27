from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.models.student import Student, StudentSummary
from app.services import data_service
from app.web import build_url, templates, wants_html

router = APIRouter(prefix='/data', tags=['Students'])


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
        'major': major,
        'city': city,
        'status': status,
        'min_gpa': min_gpa,
        'max_gpa': max_gpa,
        'page': page,
        'page_size': page_size,
    }


def parse_optional_float(
    value: str | None,
    field_name: str,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        parsed = float(cleaned)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    'type': 'float_parsing',
                    'loc': ['query', field_name],
                    'msg': 'Input should be a valid number.',
                    'input': value,
                }
            ],
        ) from exc

    if parsed < minimum or parsed > maximum:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    'type': 'value_error',
                    'loc': ['query', field_name],
                    'msg': f'Input should be between {minimum} and {maximum}.',
                    'input': value,
                }
            ],
        )

    return parsed


@router.get('/', summary='Get all students (paginated + filterable)')
def get_all_students(
    request: Request,
    major: str | None = Query(None, description='Filter by major (partial match)'),
    city: str | None = Query(None, description='Filter by city (partial match)'),
    status: str | None = Query(None, description='Filter by status: Paid | Pending | Overdue'),
    min_gpa: str | None = Query(None, description='Minimum GPA (leave blank to ignore)'),
    max_gpa: str | None = Query(None, description='Maximum GPA (leave blank to ignore)'),
    page: int = Query(1, ge=1, description='Page number'),
    page_size: int = Query(20, ge=1, le=100, description='Records per page'),
):
    min_gpa_value = parse_optional_float(min_gpa, 'min_gpa', 0.0, 4.0)
    max_gpa_value = parse_optional_float(max_gpa, 'max_gpa', 0.0, 4.0)

    result = data_service.filter_students(
        major=major,
        city=city,
        status=status,
        min_gpa=min_gpa_value,
        max_gpa=max_gpa_value,
        page=page,
        page_size=page_size,
    )

    if wants_html(request):
        filters = build_filter_params(
            major,
            city,
            status,
            min_gpa_value,
            max_gpa_value,
            page,
            page_size,
        )
        prev_url = None
        next_url = None
        if result['page'] > 1:
            prev_url = build_url(request.url.path, {**filters, 'page': result['page'] - 1})
        if result['page'] < result['total_pages']:
            next_url = build_url(request.url.path, {**filters, 'page': result['page'] + 1})

        return templates.TemplateResponse(
            request=request,
            name='students.html',
            context={
                'result': result,
                'students': result['data'],
                'filters': filters,
                'json_url': build_url(request.url.path, {**filters, 'format': 'json'}),
                'prev_url': prev_url,
                'next_url': next_url,
            },
        )

    return result


@router.get('/summary', response_model=StudentSummary, summary='Get MySQL-backed dataset summary statistics')
def get_summary(request: Request):
    summary = data_service.get_summary()

    if wants_html(request):
        preview = data_service.filter_students(page=1, page_size=5)['data']
        return templates.TemplateResponse(
            request=request,
            name='summary.html',
            context={
                'summary': summary,
                'preview': preview,
                'json_url': build_url(request.url.path, {'format': 'json'}),
                'source': data_service.get_source_details(),
            },
        )

    return summary


@router.get('/reload', summary='Open the CSV-to-MySQL sync page', response_class=HTMLResponse)
def reload_page(request: Request):
    source = data_service.get_source_details()

    try:
        summary = data_service.get_summary()
        message = None
        is_error = False
    except Exception as exc:
        summary = {'total': 0, 'status_breakdown': {}}
        message = str(exc)
        is_error = True

    return templates.TemplateResponse(
        request=request,
        name='reload.html',
        context={
            'message': message,
            'is_error': is_error,
            'total_records': summary['total'],
            'status_breakdown': summary['status_breakdown'],
            'source': source,
        },
    )


@router.post('/reload', summary='Sync CSV data into MySQL')
def reload_data(request: Request):
    source = data_service.get_source_details()

    try:
        data = data_service.reload_data()
        payload = {
            'message': (
                f"Synced {len(data)} records from {source['csv_path']} "
                f"into MySQL table {source['database']}.{source['table_name']}."
            ),
            'total_records': len(data),
        }
        summary = data_service.get_summary()
    except Exception as exc:
        if wants_html(request):
            return templates.TemplateResponse(
                request=request,
                name='reload.html',
                context={
                    'message': str(exc),
                    'is_error': True,
                    'total_records': 0,
                    'status_breakdown': {},
                    'source': source,
                },
                status_code=500,
            )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if wants_html(request):
        return templates.TemplateResponse(
            request=request,
            name='reload.html',
            context={
                **payload,
                'is_error': False,
                'status_breakdown': summary['status_breakdown'],
                'source': source,
            },
        )

    return payload


@router.get('/{student_id}', response_model=Student, summary='Get student by ID')
def get_student(request: Request, student_id: str):
    student = data_service.get_student_by_id(student_id)
    if not student:
        if wants_html(request):
            return templates.TemplateResponse(
                request=request,
                name='student_detail.html',
                context={
                    'student': None,
                    'student_id': student_id,
                    'json_url': build_url(request.url.path, {'format': 'json'}),
                },
                status_code=404,
            )
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")

    if wants_html(request):
        return templates.TemplateResponse(
            request=request,
            name='student_detail.html',
            context={
                'student': student,
                'student_id': student_id,
                'json_url': build_url(request.url.path, {'format': 'json'}),
            },
        )

    return student
