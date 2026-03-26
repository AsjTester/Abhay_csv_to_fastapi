from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def wants_html(request: Request) -> bool:
    format_hint = request.query_params.get("format")
    if format_hint == "html":
        return True
    if format_hint == "json":
        return False

    accept = request.headers.get("accept", "").lower()
    return "text/html" in accept or "application/xhtml+xml" in accept


def build_url(path: str, params: dict) -> str:
    clean_params = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }
    query = urlencode(clean_params)
    return f"{path}?{query}" if query else path
