import math
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

VERSION = os.getenv("APP_VERSION", "1.1.0")

app = FastAPI(
    title="Calculator API",
    description="Простой API-калькулятор",
    version=VERSION,
)


class Operands(BaseModel):
    a: float = Field(..., description="Первое число", allow_inf_nan=False)
    b: float = Field(..., description="Второе число", allow_inf_nan=False)


class Result(BaseModel):
    operation: str
    a: float
    b: float
    result: float


def _respond(op: str, data: Operands, value: float) -> Result:
    if math.isinf(value) or math.isnan(value):
        raise HTTPException(status_code=422, detail="Результат выходит за допустимые пределы")
    return Result(operation=op, a=data.a, b=data.b, result=value)


STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": VERSION}


@app.post("/add", response_model=Result)
def add(data: Operands):
    return _respond("add", data, data.a + data.b)


@app.post("/subtract", response_model=Result)
def subtract(data: Operands):
    return _respond("subtract", data, data.a - data.b)


@app.post("/multiply", response_model=Result)
def multiply(data: Operands):
    return _respond("multiply", data, data.a * data.b)


@app.post("/divide", response_model=Result)
def divide(data: Operands):
    if data.b == 0:
        raise HTTPException(status_code=400, detail="Деление на ноль")
    return _respond("divide", data, data.a / data.b)
