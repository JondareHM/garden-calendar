#!/usr/bin/env python3
"""Insert a clear year divider into each bed card in the generated overview."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "index.html"

MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

SECTION_RE = re.compile(r'(<section class="bed">.*?</section>)', re.DOTALL)
EVENT_RE = re.compile(
    r'(<div class="event [^"]+">.*?</div>|<details class="event [^"]+">.*?</details>)',
    re.DOTALL,
)
DATE_RE = re.compile(r'<span class="date">\d+\.\s+([A-Z][a-z]{2})')


def add_dividers(section: str, start_year: int) -> str:
    events = list(EVENT_RE.finditer(section))
    if not events:
        return section

    current_year = start_year
    previous_month: int | None = None
    offset = 0
    result = section

    for match in events:
        date_match = DATE_RE.search(match.group(0))
        if not date_match:
            continue
        month = MONTHS.get(date_match.group(1))
        if month is None:
            continue

        if previous_month is not None and month < previous_month:
            current_year += 1
            divider = (
                f'<div class="year-divider"><span>{current_year}</span>'
                '<small>Normal årsplan</small></div>'
            )
            insert_at = match.start() + offset
            result = result[:insert_at] + divider + result[insert_at:]
            offset += len(divider)
        previous_month = month

    return result


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    generated_match = re.search(r'genereret\s+(\d{2})-(\d{2})-(\d{4})', html)
    start_year = int(generated_match.group(3)) if generated_match else date.today().year

    html = SECTION_RE.sub(lambda match: add_dividers(match.group(1), start_year), html)
    css = (
        '.year-divider{display:flex;align-items:center;gap:9px;margin:13px -4px 5px;'
        'padding:7px 9px;border-top:3px solid var(--green);border-bottom:1px solid var(--line);'
        'background:#f3f7f1;color:var(--green)}'
        '.year-divider span{font-size:18px;font-weight:800}.year-divider small{font-weight:650;letter-spacing:.02em}'
        '@media print{.year-divider{margin-top:8px;padding:4px 7px;break-after:avoid}}'
    )
    html = html.replace('</style>', css + '</style>', 1)
    HTML_PATH.write_text(html, encoding="utf-8")
    print("Tilføjede tydelig adskillelse ved årsskiftet i index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
