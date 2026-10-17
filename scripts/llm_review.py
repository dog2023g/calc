#!/usr/bin/env python3
"""LLM-проверка кода на уязвимости через GitHub Models (бесплатный tier).

Сканирует все файлы в SCAN_DIR, пишет report.md и GitHub Step Summary.
"""
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
 
 
def need(name):
    value = os.getenv(name, "").strip()
    if not value:
        sys.exit(f"Не задана переменная окружения {name}")
    return value
 
 
API_URL = need("LLM_BASE_URL").rstrip("/") + "/chat/completions"
MODEL = need("LLM_MODEL")
TOKEN = need("LLM_API_KEY")
SCAN_DIR = pathlib.Path(os.getenv("SCAN_DIR", "app"))
EXTS = {".py", ".js", ".html"}
MAX_CHARS = int(os.getenv("MAX_CHARS", "12000"))
PAUSE = float(os.getenv("PAUSE_SEC", "4"))
FAIL_ON_HIGH = os.getenv("FAIL_ON_HIGH", "false").lower() == "true"
 
SYSTEM = (
    "Ты эксперт по безопасности приложений. Проанализируй код на уязвимости "
    "(OWASP Top 10, CWE): инъекции (в том числе command injection и RCE), XSS, "
    "SSRF, path traversal, небезопасная десериализация, секреты в коде, слабая "
    "криптография, небезопасные настройки, отсутствие валидации ввода. "
    "Не выдумывай проблемы: если уязвимостей нет, верни пустой список. "
    "Ответь строго JSON без пояснений и без markdown: "
    '{"findings":[{"line":<int>,"severity":"CRITICAL|HIGH|MEDIUM|LOW",'
    '"cwe":"CWE-xxx","title":"...","explanation":"...","fix":"..."}]}. '
    "Тексты на русском."
)
 
 
def chunks(text):
    """Режет файл на куски по строкам, возвращает (номер_первой_строки, строки)."""
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
    """Достаёт JSON из ответа модели, даже если он обёрнут в ```json или think-теги."""
    text = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("в ответе модели нет JSON")
    data = json.loads(text[start : end + 1])
    findings = data.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("поле findings не является списком")
    return [f for f in findings if isinstance(f, dict)]
 
 
def retry_after(err, attempt):
    try:
        return min(int(err.headers.get("Retry-After")), 120)
    except (TypeError, ValueError):
        return 30 * (attempt + 1)
 
 
def ask(path, start, lines):
    """Возвращает (findings, None) при успехе или (None, причина_ошибки)."""
    numbered = "\n".join(f"{start + i}: {l}" for i, l in enumerate(lines))
    body = json.dumps(
        {
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Файл: {path}\n\n{numbered}"},
            ],
        }
    ).encode()
    last_err = "неизвестная ошибка"
    for attempt in range(4):
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                # у стандартного User-Agent urllib некоторые API отвечают 403
                "User-Agent": "llm-security-review/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                status = r.status
                ctype = r.headers.get("Content-Type", "")
                raw = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            last_err = f"HTTP {e.code}: {detail}"
            if e.code == 429 or e.code >= 500:  # лимит или сбой сервера — повторяем
                wait = retry_after(e, attempt)
                print(f"{last_err}. Жду {wait}с и повторяю", file=sys.stderr)
                time.sleep(wait)
                continue
            return None, last_err
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = f"сетевая ошибка: {e}"
            print(f"{last_err}. Повторяю", file=sys.stderr)
            time.sleep(5)
            continue
 
        try:
            choice = json.loads(raw)["choices"][0]
        except (ValueError, KeyError, IndexError, TypeError):
            return None, (
                f"неожиданный ответ API (HTTP {status}, {ctype or 'без Content-Type'}): "
                f"{raw[:300]!r}"
            )
        content = (choice.get("message") or {}).get("content")
        try:
            return parse_findings(content), None
        except ValueError as e:
            return None, (
                f"не удалось разобрать ответ модели ({e}); "
                f"finish_reason={choice.get('finish_reason')}; "
                f"ответ: {(content or '')[:300]!r}"
            )
    return None, last_err
 
 
def main():
    files = sorted(
        p
        for p in SCAN_DIR.rglob("*")
        if p.is_file() and p.suffix in EXTS and "__pycache__" not in p.parts
    )
    report = [
        f"# LLM Security Review\n\nМодель: `{MODEL}`, файлов: {len(files)}\n",
    ]
    high = 0
    errors = 0
 
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        report.append(f"\n## `{path}`\n")
        if not text.strip():
            report.append("Файл пуст, пропущен.\n")
            continue
 
        findings = []
        failures = []
        for start, lines in chunks(text):
            res, err = ask(path, start, lines)
            time.sleep(PAUSE)
            if err:
                errors += 1
                end = start + len(lines) - 1
                clean = err.replace("`", "'").replace("\n", " ")
                failures.append(f"  - строки {start}–{end}: {clean}")
                print(f"[ОШИБКА] {path} строки {start}–{end}: {err}", file=sys.stderr)
                continue
            findings += res
 
        if failures:
            report.append(
                "Анализ не удался, результат неполный. Причины:\n"
                + "\n".join(failures)
                + "\n"
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
