# Калькулятор API

Доступен на сайте: <https://calc-0ao5.onrender.com/>. Возможно потребуется 1 минута ожидания для холодного старта сайта, затем работает без проблем.
REST API-калькулятор на FastAPI, упакованный в Docker.

## Эндпоинты

| Метод | Путь         | Описание                     |
|-------|--------------|------------------------------|
| GET   | /health      | проверка работоспособности   |
| GET   | /version     | версия приложения            |
| POST  | /add         | a + b                        |
| POST  | /subtract    | a - b                        |
| POST  | /multiply    | a * b                        |
| POST  | /divide      | a / b (b ≠ 0)                |

Тело запроса: `{"a": 10, "b": 4}`. Веб-интерфейс: `http://localhost:8000/` (обращается к API через fetch). Swagger-документация: `/docs`.

## Запуск в Docker

```bash
docker build -t calculator-api:1.1.0 .
docker run -d --name calc -p 8000:8000 calculator-api:1.1.0
curl -X POST localhost:8000/divide -H "Content-Type: application/json" -d '{"a":10,"b":4}'
```

Остановка: `docker rm -f calc`


