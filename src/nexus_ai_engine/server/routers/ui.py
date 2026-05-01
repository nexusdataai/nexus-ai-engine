"""UI router — serves the embedded React journey studio.

``/`` redirects to ``/ui``. ``/ui`` returns the single-page ``index.html``.
Static assets live under ``/ui/assets/*`` and come from the in-package
``static/ui/`` directory (shipped inside the wheel).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "ui"


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui", status_code=307)


@router.get("/ui", include_in_schema=False)
async def ui_root() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=500, detail=f"UI assets not found at {STATIC_DIR}")
    return FileResponse(index, media_type="text/html")


def mount_ui(app: FastAPI) -> None:
    """Mount the static asset directory at /ui/assets."""
    if STATIC_DIR.exists():
        app.mount(
            "/ui/assets",
            StaticFiles(directory=STATIC_DIR, check_dir=False),
            name="ui-assets",
        )
