import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = BASE_DIR / 'data' / 'students_complete.csv'
STUDENT_COLUMNS = [
    'student_id',
    'first_name',
    'last_name',
    'age',
    'major',
    'gpa',
    'attendance',
    'scholarship',
    'city',
    'status',
]


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('`', '``')
    return f'`{escaped}`'


def _sanitize_identifier(value: str) -> str:
    sanitized = re.sub(r'\W+', '_', value.strip().lower()).strip('_')
    if not sanitized:
        raise ValueError('The CSV filename must contain at least one letter or number.')
    return sanitized


def get_data_path() -> Path:
    configured_path = os.getenv('CSV_FILE_PATH')
    if not configured_path:
        return DEFAULT_DATA_PATH

    candidate = Path(configured_path)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate.resolve()


def get_table_name() -> str:
    return _sanitize_identifier(get_data_path().stem)


def get_mysql_settings() -> dict:
    port_raw = os.getenv('MYSQL_PORT', '3306')
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f'MYSQL_PORT must be an integer. Received: {port_raw}') from exc

    return {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': port,
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE', 'csv_fastapi'),
    }


def get_source_details() -> dict:
    settings = get_mysql_settings()
    return {
        'csv_path': str(get_data_path()),
        'table_name': get_table_name(),
        'database': settings['database'],
        'host': settings['host'],
        'port': settings['port'],
    }


def _server_url(settings: dict) -> URL:
    return URL.create(
        'mysql+pymysql',
        username=settings['user'],
        password=settings['password'],
        host=settings['host'],
        port=settings['port'],
    )


def _database_url(settings: dict) -> URL:
    return URL.create(
        'mysql+pymysql',
        username=settings['user'],
        password=settings['password'],
        host=settings['host'],
        port=settings['port'],
        database=settings['database'],
    )


def _build_database_engine(settings: dict) -> Engine:
    return create_engine(_database_url(settings), future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_mysql_settings()
    database_engine = _build_database_engine(settings)

    try:
        with database_engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return database_engine
    except Exception as exc:
        message = str(exc).lower()
        database_engine.dispose()
        database_missing = 'unknown database' in message or '1049' in message
        if not database_missing:
            raise RuntimeError(
                'Unable to connect to the MySQL database. '
                'Update MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE as needed. '
                f"Attempted {settings['host']}:{settings['port']}/{settings['database']}. Original error: {exc}"
            ) from exc

    server_engine = None
    try:
        server_engine = create_engine(_server_url(settings), future=True, pool_pre_ping=True)
        with server_engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS {_quote_identifier(settings['database'])} "
                    'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
                )
            )
    except Exception as exc:
        raise RuntimeError(
            'Unable to create the configured MySQL database. '
            'Make sure MySQL is running and the configured user can create databases, or create the database manually first. '
            f"Attempted {settings['host']}:{settings['port']}/{settings['database']}. Original error: {exc}"
        ) from exc
    finally:
        if server_engine is not None:
            server_engine.dispose()

    database_engine = _build_database_engine(settings)
    try:
        with database_engine.connect() as connection:
            connection.execute(text('SELECT 1'))
    except Exception as exc:
        database_engine.dispose()
        raise RuntimeError(
            'The MySQL database was created, but the app could not reconnect to it. '
            f"Attempted {settings['host']}:{settings['port']}/{settings['database']}. Original error: {exc}"
        ) from exc

    return database_engine


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = normalized.columns.str.strip().str.lower().str.replace(' ', '_')

    if 'major' in normalized.columns:
        normalized['major'] = normalized['major'].map(
            lambda value: value.strip().title() if isinstance(value, str) else value
        )

    return normalized.astype(object).where(pd.notna(normalized), other=None)


def _normalize_text_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def _load_csv_records() -> list[dict]:
    data_path = get_data_path()
    if not data_path.exists():
        raise FileNotFoundError(f'CSV file not found at: {data_path}')

    frame = pd.read_csv(data_path)
    normalized = _normalize_frame(frame)

    missing_columns = [column for column in STUDENT_COLUMNS if column not in normalized.columns]
    if missing_columns:
        missing = ', '.join(missing_columns)
        raise RuntimeError(f'CSV is missing required columns: {missing}')

    return normalized.loc[:, STUDENT_COLUMNS].to_dict(orient='records')


def _create_students_table(connection: Connection) -> None:
    table_name = get_table_name()
    quoted_table = _quote_identifier(table_name)
    index_major = _quote_identifier(f'idx_{table_name}_major')
    index_city = _quote_identifier(f'idx_{table_name}_city')
    index_status = _quote_identifier(f'idx_{table_name}_status')

    connection.execute(
        text(
            f'''
            CREATE TABLE IF NOT EXISTS {quoted_table} (
                student_id VARCHAR(50) PRIMARY KEY,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                age INT NULL,
                major VARCHAR(100) NULL,
                gpa DOUBLE NULL,
                attendance DOUBLE NULL,
                scholarship DOUBLE NULL,
                city VARCHAR(100) NULL,
                status VARCHAR(50) NULL,
                INDEX {index_major} (major),
                INDEX {index_city} (city),
                INDEX {index_status} (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            '''
        )
    )


def _fetch_rows(sql: str, params: Optional[dict] = None) -> list[dict]:
    with get_engine().connect() as connection:
        result = connection.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]


def load_data() -> list[dict]:
    return sync_csv_to_mysql()


def reload_data() -> list[dict]:
    return sync_csv_to_mysql()


def sync_csv_to_mysql() -> list[dict]:
    records = _load_csv_records()
    table_name = _quote_identifier(get_table_name())
    columns_sql = ', '.join(STUDENT_COLUMNS)
    placeholders_sql = ', '.join(f':{column}' for column in STUDENT_COLUMNS)
    insert_sql = text(
        f'INSERT INTO {table_name} ({columns_sql}) VALUES ({placeholders_sql})'
    )

    with get_engine().begin() as connection:
        _create_students_table(connection)
        connection.execute(text(f'DELETE FROM {table_name}'))
        if records:
            connection.execute(insert_sql, records)

    return get_all_students()


def get_all_students() -> list[dict]:
    table_name = _quote_identifier(get_table_name())
    columns_sql = ', '.join(STUDENT_COLUMNS)
    return _fetch_rows(
        f'SELECT {columns_sql} FROM {table_name} ORDER BY student_id'
    )


def get_student_by_id(student_id: str) -> Optional[dict]:
    table_name = _quote_identifier(get_table_name())
    columns_sql = ', '.join(STUDENT_COLUMNS)
    rows = _fetch_rows(
        f'SELECT {columns_sql} FROM {table_name} WHERE UPPER(student_id) = UPPER(:student_id) LIMIT 1',
        {'student_id': student_id},
    )
    return rows[0] if rows else None


def filter_students(
    major: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    min_gpa: Optional[float] = None,
    max_gpa: Optional[float] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    major = _normalize_text_filter(major)
    city = _normalize_text_filter(city)
    status = _normalize_text_filter(status)

    table_name = _quote_identifier(get_table_name())
    columns_sql = ', '.join(STUDENT_COLUMNS)
    conditions: list[str] = []
    params: dict = {}

    if major:
        conditions.append('LOWER(major) LIKE :major')
        params['major'] = f"%{major.lower()}%"
    if city:
        conditions.append('LOWER(city) LIKE :city')
        params['city'] = f"%{city.lower()}%"
    if status:
        conditions.append('LOWER(status) = :status')
        params['status'] = status.lower()
    if min_gpa is not None:
        conditions.append('gpa >= :min_gpa')
        params['min_gpa'] = min_gpa
    if max_gpa is not None:
        conditions.append('gpa <= :max_gpa')
        params['max_gpa'] = max_gpa

    where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ''
    count_sql = f'SELECT COUNT(*) AS total FROM {table_name}{where_sql}'
    total_row = _fetch_rows(count_sql, params)[0]
    total = int(total_row['total'])

    paginated_params = {**params, 'limit': page_size, 'offset': (page - 1) * page_size}
    data_sql = (
        f'SELECT {columns_sql} FROM {table_name}{where_sql} '
        'ORDER BY student_id LIMIT :limit OFFSET :offset'
    )
    paginated = _fetch_rows(data_sql, paginated_params)

    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'data': paginated,
    }


def get_summary() -> dict:
    table_name = _quote_identifier(get_table_name())
    summary_row = _fetch_rows(
        f'''
        SELECT
            COUNT(*) AS total,
            ROUND(AVG(gpa), 2) AS avg_gpa,
            ROUND(AVG(attendance), 2) AS avg_attendance
        FROM {table_name}
        '''
    )[0]
    status_rows = _fetch_rows(
        f'''
        SELECT COALESCE(status, 'Unknown') AS status, COUNT(*) AS count
        FROM {table_name}
        GROUP BY COALESCE(status, 'Unknown')
        ORDER BY status
        '''
    )

    avg_gpa = summary_row['avg_gpa']
    avg_attendance = summary_row['avg_attendance']

    return {
        'total': int(summary_row['total']),
        'avg_gpa': round(float(avg_gpa), 2) if avg_gpa is not None else None,
        'avg_attendance': round(float(avg_attendance), 2) if avg_attendance is not None else None,
        'status_breakdown': {
            row['status']: int(row['count'])
            for row in status_rows
        },
    }
