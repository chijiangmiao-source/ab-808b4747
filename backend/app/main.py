"""FastAPI application for tree-network acoustic leak localization."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .solver import solve
from .validation import DraftValidationError, validate_and_build

app = FastAPI(title="地下储气库树状管网泄漏定位", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "leak-localizer-api"}


@app.exception_handler(DraftValidationError)
async def draft_validation_handler(request: Request, exc: DraftValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"ok": False, "errors": [issue.as_dict() for issue in exc.issues]},
    )


@app.post("/api/localize")
def localize(payload: Dict[str, Any]) -> Dict[str, Any]:
    node_ids, edges_raw, sensors_raw = validate_and_build(payload)
    index_of = {node_id: i for i, node_id in enumerate(node_ids)}

    # solver wants compact indices and original input order preserved.
    edges = [(index_of[u], index_of[v], length) for u, v, length, _idx in edges_raw]
    sensors = [(index_of[node], time) for node, time, _idx in sensors_raw]

    result = solve(node_ids, edges, sensors)
    return {"ok": True, "result": result}


# Serve the built React app when the static bundle is present (Docker image).
_STATIC_DIR = Path(os.environ.get("STATIC_DIR", "/app/static"))
if _STATIC_DIR.is_dir() and (_STATIC_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
