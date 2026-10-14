#!/usr/bin/env python3
"""
Превращает JSON-отчёт Semgrep в markdown для GitHub Summary.
"""
import json
import sys
from collections import Counter
from pathlib import Path

MAX_ROWS = 100
SEVERITY_ORDER = {"ERROR": 0, "HIGH": 0, "WARNING": 1, "MEDIUM": 1, "INFO": 2, "LOW": 2}


def cell(text: str, limit: int = 160) -> str:
    """Одна строка без символов, ломающих markdown-таблицу."""
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main(path: str) -> None:
    report = Path(path)
    print("## Semgrep (SAST)\n")
    if not report.exists():
        print("Отчёт не найден: скан не дошёл до формирования результата.")
        return

    data = json.loads(report.read_text(encoding="utf-8"))
    results = data.get("results", [])
    errors = data.get("errors", [])

    if not results:
        print("Находок нет.")
    else:
        by_severity = Counter(r.get("extra", {}).get("severity", "UNKNOWN") for r in results)
        print("Находок: **{}** ({})\n".format(
            len(results),
            ", ".join(f"{sev}: {n}" for sev, n in sorted(
                by_severity.items(), key=lambda kv: SEVERITY_ORDER.get(kv[0], 3))),
        ))

        results.sort(key=lambda r: (
            SEVERITY_ORDER.get(r.get("extra", {}).get("severity", ""), 3),
            r.get("path", ""),
            r.get("start", {}).get("line", 0),
        ))
        print("| Уровень | Правило | Файл:строка | Описание |")
        print("|---|---|---|---|")
        for r in results[:MAX_ROWS]:
            extra = r.get("extra", {})
            location = "{}:{}".format(r.get("path", "?"), r.get("start", {}).get("line", "?"))
            print("| {} | {} | {} | {} |".format(
                cell(extra.get("severity", "?")),
                cell(r.get("check_id", "?").split(".")[-1], 60),
                cell(location, 80),
                cell(extra.get("message", "")),
            ))
        if len(results) > MAX_ROWS:
            print(f"\nПоказаны первые {MAX_ROWS} из {len(results)}, полный список в артефакте `semgrep-report`.")

    if errors:
        print(f"\nОшибок при сканировании: **{len(errors)}** (подробности в semgrep.json).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Использование: semgrep_summary.py <semgrep.json>")
    main(sys.argv[1])
