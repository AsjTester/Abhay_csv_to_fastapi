from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.routers import students
from app.services import data_service
from app.web import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        records = data_service.load_data()
        source = data_service.get_source_details()
        print(
            'MySQL sync complete - '
            f"{len(records)} records loaded from {source['csv_path']} "
            f"into {source['database']}.{source['table_name']}."
        )
    except Exception as exc:
        print(f'Startup warning: {exc}')
    yield
    print('Shutting down.')


app = FastAPI(
    title='Student Data API',
    description=(
        'A FastAPI service that syncs student records from a CSV file into a MySQL table '
        'and exposes endpoints for fetching, filtering, searching, and summarizing the data.\n\n'
        'Built for Project-K by Team AJ.'
    ),
    version='1.1.0',
    lifespan=lifespan,
)


def build_home_context() -> dict:
    source = data_service.get_source_details()

    try:
        summary = data_service.get_summary()
        students_preview = data_service.filter_students(page=1, page_size=8)['data']
        load_error = None
    except Exception as exc:
        summary = {
            'total': 0,
            'avg_gpa': None,
            'avg_attendance': None,
            'status_breakdown': {},
        }
        students_preview = []
        load_error = str(exc)

    example_links = [
        {'label': 'All students', 'url': '/data/'},
        {'label': 'Data science GPA 3.0+', 'url': '/data/?major=data+science&min_gpa=3.0'},
        {'label': 'Seattle paid students', 'url': '/data/?city=seattle&status=Paid'},
        {'label': 'Student STU_1000', 'url': '/data/STU_1000'},
        {'label': 'Dataset summary', 'url': '/data/summary'},
        {'label': 'Sync CSV to MySQL', 'url': '/data/reload'},
    ]

    return {
        'summary': summary,
        'students': students_preview,
        'load_error': load_error,
        'example_links': example_links,
        'source': source,
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={'detail': f'Internal server error: {str(exc)}'},
    )


app.include_router(students.router)


@app.get('/', tags=['Frontend'], response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context=build_home_context(),
    )


@app.get('/health', tags=['Health'])
def health():
    source = data_service.get_source_details()

    try:
        summary = data_service.get_summary()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                'status': 'unhealthy',
                'database': source['database'],
                'table': source['table_name'],
                'csv_path': source['csv_path'],
                'detail': str(exc),
            },
        )

    return {
        'status': 'healthy',
        'database': source['database'],
        'table': source['table_name'],
        'csv_path': source['csv_path'],
        'records': summary['total'],
    }
