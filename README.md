# Калькулятор API

Доступен на сайте: <https://calc-0ao5.onrender.com/> (версия без уязвимостей). Возможно потребуется 1 минута ожидания для холодного старта сайта, затем работает без проблем.

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

## Эндпоинты у уязвимой версии
| Эндпоинт | Описание |
|---|---|
| `POST /mod` | Остаток от деления |
| `POST /evaluate` | Расчет сложных выражений со скобочками |
| `POST /comment`, `GET /comment` | Добавление и чтение комментариев для пользователя |
| `POST /formula` | Калькулятор с более структурированным вводом |

## Запуск в Docker

```bash
docker build -t calculator-api:1.1.0 .
docker run -d --name calc -p 8000:8000 calculator-api:1.1.0
curl -X POST localhost:8000/divide -H "Content-Type: application/json" -d '{"a":10,"b":4}'
```

Остановка: `docker rm -f calc`

## CI/CD-пайплайн

При каждом пуше в `main` GitHub Actions (`.github/workflows/ci-cd.yml`) выполняет:

1. **Тесты** — `pytest` на эндпоинтах.
2. **Повышение версии** — `scripts/version_up.py` смотрит на сообщение последнего коммита (стиль [Conventional Commits]) и обновляет файл `VERSION`:
   - `fix: ...` → patch;
   - `feat: ...` → minor (например, добавлен новый метод API);
   - `feat!: ...` или `BREAKING CHANGE` в сообщении → major;
   - всё остальное → patch.
   Новый `VERSION` коммитится ботом в `main` с пометкой `[skip ci]`, чтобы не запускать пайплайн повторно, и ставится git-тег `vX.Y.Z`.
3. **Сборка и публикация образа** — Docker-образ собирается уже с обновлённым `VERSION` внутри и публикуется в GitHub Container Registry: `ghcr.io/<owner>/<repo>:X.Y.Z` и `:latest`.

P.S.
После добавления уязвимых эндпоинтов в калькулятор пайплайн **не деплоит на Render автоматически**
