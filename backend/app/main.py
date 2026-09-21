"""FastAPI service for exact minimax leak localization."""
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .solver import SolveError, solve

app = FastAPI(
    title="地下储气库管网泄漏定位 API",
    description="在树状管网上以精确有理数最小化传感器最大绝对残差，"
                "求全部规范源点/闭区间。",
    version="1.0.0",
)

_cors = os.getenv("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "leak-locator-api"}


@app.get("/api/v1/limits")
def limits():
    from . import solver as s
    return {
        "nodes": {"min": s.MIN_NODES, "max": s.MAX_NODES},
        "sensors": {"min": s.MIN_SENSORS, "max": s.MAX_SENSORS},
        "edge_length_max": s.MAX_LENGTH,
        "arrival_abs_max": s.MAX_ABS_ARRIVAL,
        "id_max_length": s.MAX_ID_LEN,
    }


@app.post("/api/v1/locate")
async def locate(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"status": "error",
                     "errors": [{"code": "BAD_JSON",
                                 "message": "请求体不是合法 JSON",
                                 "field": "body"}]},
        )
    started = time.perf_counter()
    try:
        result = solve(payload)
    except SolveError as ex:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "errors": ex.errors},
        )
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result
