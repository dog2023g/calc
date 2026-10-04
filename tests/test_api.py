from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_add():
    r = client.post("/add", json={"a": 2, "b": 3})
    assert r.status_code == 200 and r.json()["result"] == 5


def test_subtract():
    assert client.post("/subtract", json={"a": 5, "b": 3}).json()["result"] == 2


def test_multiply():
    assert client.post("/multiply", json={"a": 4, "b": 2.5}).json()["result"] == 10


def test_divide():
    assert client.post("/divide", json={"a": 10, "b": 4}).json()["result"] == 2.5


def test_divide_by_zero():
    assert client.post("/divide", json={"a": 1, "b": 0}).status_code == 400


def test_invalid_input():
    assert client.post("/add", json={"a": "abc", "b": 1}).status_code == 422


def test_mod_computes_remainder():
    r = client.post("/mod", json={"a": "10", "b": "3"})
    assert r.status_code == 200
    assert r.json()["result"] == "1"


def test_mod_negative_dividend():
    r = client.post("/mod", json={"a": "-7", "b": "3"})
    assert r.status_code == 200
    assert r.json()["result"] == "-1"


def test_evaluate_simple_expression():
    r = client.post("/evaluate", json={"expression": "2 + 2"})
    assert r.status_code == 200
    assert r.json()["result"] == 4


def test_evaluate_power_expression():
    r = client.post("/evaluate", json={"expression": "2 ** 8"})
    assert r.status_code == 200
    assert r.json()["result"] == 256


def test_evaluate_difficult_expression():
    r = client.post("/evaluate", json={"expression": "(2*(3 + 5) - 6) ** 2"})
    assert r.status_code == 200
    assert r.json()["result"] == 100


def test_formula_add_from_yaml():
    r = client.post("/formula", json={"yaml_config": "a: 2\nb: 3\nop: add"})
    assert r.status_code == 200
    body = r.json()
    assert body["operation"] == "add"
    assert body["result"] == 5.0
