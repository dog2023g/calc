import math
import os
from pathlib import Path
import yaml
import subprocess

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
_FILE_VERSION = _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else "0.0.0"
# APP_VERSION в окружении, если задан явно, имеет приоритет над файлом VERSION
VERSION = os.getenv("APP_VERSION", _FILE_VERSION)


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


class ModInput(BaseModel):
    a: str = Field(..., description="Делимое (строка!)")
    b: str = Field(..., description="Делитель (строка!)")


@app.post("/mod")
def modulo(data: ModInput):
    command = f"echo $(( {data.a} % {data.b} ))"
    proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
    return {"operation": "mod", "a": data.a, "b": data.b, "result": proc.stdout.strip(), "stderr": proc.stderr.strip()}


class ExprInput(BaseModel):
    expression: str = Field(..., description="Произвольное математическое выражение")


@app.post("/evaluate")
def evaluate_expression(data: ExprInput):
    result = eval(data.expression)
    return {"expression": data.expression, "result": result}

_comments_by_session: dict[str, list[str]] = {}


def _session_id(request: Request, response: Response) -> str:
    sid = request.cookies.get("sid")
    if not sid:
        sid = secrets.token_hex(16)
    response.set_cookie("sid", sid, httponly=True, samesite="lax")
    return sid


class CommentInput(BaseModel):
    text: str


@app.post("/comment", response_class=HTMLResponse)
def add_comment(data: CommentInput, request: Request, response: Response):
    sid = _session_id(request, response)
    _comments_by_session.setdefault(sid, []).append(data.text)
    items = "".join(f"<li>{c}</li>" for c in _comments_by_session[sid])
    return f"<ul>{items}</ul>"


@app.get("/comment", response_class=HTMLResponse)
def list_comments(request: Request, response: Response):
    sid = _session_id(request, response)
    items = "".join(f"<li>{c}</li>" for c in _comments_by_session.get(sid, []))
    return f"<ul>{items}</ul>"

class FormulaInput(BaseModel):
    yaml_config: str = Field(
        ..., description="YAML вида 'a: 2\\nb: 3\\nop: add'"
    )


@app.post("/formula")
def formula_from_yaml(data: FormulaInput):
    cfg = yaml.load(data.yaml_config, Loader=yaml.Loader)
    a = float(cfg.get("a", 0))
    b = float(cfg.get("b", 0))
    op = cfg.get("op", "add")
    ops = {"add": a + b, "subtract": a - b, "multiply": a * b, "divide": a / b if b else None}
    return {"config": cfg, "operation": op, "result": ops.get(op)}



