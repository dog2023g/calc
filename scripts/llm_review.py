#!/usr/bin/env python3
"""LLM-проверка кода на уязвимости через GitHub Models (бесплатный tier).

Сканирует все файлы в SCAN_DIR, пишет report.md и GitHub Step Summary.
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://models.github.ai/inference/chat/completions"
MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
SCAN_DIR = pathlib.Path(os.getenv("SCAN_DIR", "app"))
EXTS = {".py", ".js", ".html"}
MAX_CHARS = int(os.getenv("MAX_CHARS", "12000"))  # размер куска кода за запрос
PAUSE = float(os.getenv("PAUSE_SEC", "4"))  # пауза между запросами (лимиты free tier)
FAIL_ON_HIGH = os.getenv("FAIL_ON_HIGH", "false").lower() == "true"
TOKEN = os.environ["GITHUB_TOKEN"]

SYSTEM = (
    "Ты эксперт по безопасности приложений. Проанализируй код на уязвимости "
    "(OWASP Top 10, CWE): инъекции, XSS, SSRF, path traversal, небезопасная "
    "десериализация, секреты в коде, слабая криптография, небезопасные настройки, "
    "отсутствие валидации ввода. Не выдумывай проблемы: если уязвимостей нет, "
    "верни пустой список. Ответь строго JSON без пояснений: "
    '{"findings":[{"line":<int>,"severity":"CRITICAL|HIGH|MEDIUM|LOW",'
    '"cwe":"CWE-xxx","title":"...","explanation":"...","fix":"..."}]}. '
    "Тексты на русском."
)


def chunks(text):
    """Режет файл на куски по строкам, возвращает (номер_первой_строки, текст)."""
    lines = text.splitlines()
    start, buf, size = 1, [], 0
    for i, line in enumerate(lines, 1):
        if size + len(line) > MAX_CHARS and buf:
            yield start, buf
            start, buf, size = i, [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        yield start, buf


def parse_findings(content):
    """Достаёт JSON из ответа модели, даже если он обёрнут в ```json ... ```."""
    text = (content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("в ответе нет JSON")
    data = json.loads(text[start : end + 1])
    return data.get("findings", [])


def ask(path, start, lines):
    numbered = "\n".join(f"{start + i}: {l}" for i, l in enumerate(lines))
    body = json.dumps(
        {
            "model": MODEL,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Файл: {path}\n\n{numbered}"},
            ],
        }
    ).encode()
    for attempt in range(4):
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode("utf-8", errors="replace")
            try:
                choice = json.loads(raw)["choices"][0]
            except (ValueError, KeyError, IndexError):
                print(f"Неожиданный ответ API для {path}: {raw[:500]!r}", file=sys.stderr)
                return None
            content = (choice.get("message") or {}).get("content")
            try:
                return parse_findings(content)
            except ValueError as e:
                print(
                    f"Не разобрать ответ для {path} "
                    f"(finish_reason={choice.get('finish_reason')}): {e}\n"
                    f"Ответ модели: {(content or '')[:500]!r}",
                    file=sys.stderr,
                )
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429:  # лимит free tier — ждём и повторяем
                wait = int(e.headers.get("Retry-After", 30 * (attempt + 1)))
                print(f"429, жду {wait}с", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"HTTP {e.code} для {path}: {e.read()[:300]!r}", file=sys.stderr)
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"Сетевая ошибка для {path}: {e}", file=sys.stderr)
            time.sleep(5)
    return None


def main():
    files = sorted(
        p
        for p in SCAN_DIR.rglob("*")
        if p.is_file() and p.suffix in EXTS and "__pycache__" not in p.parts
    )
    report = [f"# LLM Security Review\n\nМодель: `{MODEL}`, файлов: {len(files)}\n"]
    high = 0
    errors = 0

    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        findings = []
        failed = 0
        for start, lines in chunks(text):
            res = ask(path, start, lines)
            time.sleep(PAUSE)
            if res is None:
                errors += 1
                failed += 1
                continue
            findings += res
        report.append(f"\n## `{path}`\n")
        if failed:
            report.append(
                f"⚠️ Анализ не удался для частей файла: {failed}. Результат неполный.\n"
            )
        elif not findings:
            report.append("Проблем не найдено.\n")
        for f in findings:
            sev = str(f.get("severity", "?")).upper()
            if sev in ("CRITICAL", "HIGH"):
                high += 1
            report.append(
                f"- **[{sev}] {f.get('title', '')}** "
                f"({f.get('cwe', '')}, строка {f.get('line', '?')})\n"
                f"  - {f.get('explanation', '')}\n"
                f"  - Исправление: {f.get('fix', '')}\n"
            )

    report.append(f"\n---\nCRITICAL/HIGH: **{high}**, ошибок запросов: {errors}\n")
    out = "\n".join(report)
    pathlib.Path("report.md").write_text(out, encoding="utf-8")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(out)
    print(out)

    if errors:  # не прячем сбой анализа за зелёным статусом
        sys.exit(1)
    if FAIL_ON_HIGH and high:
        sys.exit(1)


if __name__ == "__main__":
    main()