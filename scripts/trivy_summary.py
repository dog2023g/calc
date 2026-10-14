#!/usr/bin/env python3
"""
Превращает JSON-отчёт Trivy (trivy image --format json) в markdown для GitHub Summary.
"""
import json
import sys
from collections import Counter
from pathlib import Path

MAX_ROWS = 100
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
SEVERITY_ORDER = {name: i for i, name in enumerate(SEVERITIES)}


def cell(text: str, limit: int = 100) -> str:
    """Одна строка без символов, ломающих markdown-таблицу."""
    text = " ".join(str(text or "").split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def collect(results: list) -> tuple[list, list]:
    vulns, secrets = [], []
    for result in results:
        where = result.get("Type") or result.get("Class") or "?"
        # Vulnerabilities и Secrets могут отсутствовать или быть null
        for v in result.get("Vulnerabilities") or []:
            vulns.append({**v, "_where": where})
        for s in result.get("Secrets") or []:
            secrets.append({**s, "_target": result.get("Target", "?")})
    return vulns, secrets


def main(path: str) -> None:
    report = Path(path)
    print("## Trivy (анализ образа)\n")
    if not report.exists():
        print("Отчёт не найден: скан не дошёл до формирования результата.")
        return

    data = json.loads(report.read_text(encoding="utf-8"))
    vulns, secrets = collect(data.get("Results") or [])
    print(f"Образ: `{data.get('ArtifactName', '?')}`\n")

    if not vulns:
        print("Уязвимых зависимостей не найдено.")
    else:
        counts = Counter(v.get("Severity", "UNKNOWN") for v in vulns)
        fixable = sum(1 for v in vulns if v.get("FixedVersion"))
        print("Уязвимостей: **{}** ({}), из них с исправлением: **{}**\n".format(
            len(vulns),
            ", ".join(f"{s}: {counts[s]}" for s in SEVERITIES if counts[s]),
            fixable,
        ))

        # сначала критичные, внутри уровня - те, что можно исправить обновлением
        vulns.sort(key=lambda v: (
            SEVERITY_ORDER.get(v.get("Severity", "UNKNOWN"), len(SEVERITIES)),
            not v.get("FixedVersion"),
            v.get("PkgName", ""),
            v.get("VulnerabilityID", ""),
        ))
        print("| Уровень | CVE | Пакет | Версия | Исправлено в | Где | Описание |")
        print("|---|---|---|---|---|---|---|")
        for v in vulns[:MAX_ROWS]:
            vuln_id = cell(v.get("VulnerabilityID", "?"), 40)
            url = v.get("PrimaryURL")
            print("| {} | {} | {} | {} | {} | {} | {} |".format(
                cell(v.get("Severity", "?"), 12),
                f"[{vuln_id}]({url})" if url else vuln_id,
                cell(v.get("PkgName", "?"), 40),
                cell(v.get("InstalledVersion", "?"), 30),
                cell(v.get("FixedVersion") or "нет", 30),
                cell(v.get("_where", "?"), 20),
                cell(v.get("Title", "")),
            ))
        if len(vulns) > MAX_ROWS:
            print(f"\nПоказаны первые {MAX_ROWS} из {len(vulns)}, полный список в артефакте `trivy-report`.")

    if secrets:
        # само значение секрета в отчёт не выводим
        print(f"\n### Секреты в образе: {len(secrets)}\n")
        print("| Уровень | Правило | Файл |")
        print("|---|---|---|")
        for s in secrets[:MAX_ROWS]:
            print("| {} | {} | {} |".format(
                cell(s.get("Severity", "?"), 12),
                cell(s.get("Title") or s.get("RuleID", "?"), 80),
                cell(s.get("_target", "?"), 80),
            ))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Использование: trivy_summary.py <trivy.json>")
    main(sys.argv[1])
