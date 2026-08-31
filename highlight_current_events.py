#!/usr/bin/env python3
"""Add browser-side highlighting for currently relevant overview rows."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "index.html"

CSS_START = "/* current-event-highlight:start */"
CSS_END = "/* current-event-highlight:end */"
JS_START = "<!-- current-event-highlight:start -->"
JS_END = "<!-- current-event-highlight:end -->"

CSS_BLOCK = f"""{CSS_START}
.event.current{{background:#fff7d6;border:1px solid #d6bd59;border-radius:10px;padding:7px 8px;margin:4px -8px;box-shadow:0 0 0 2px #f4e8a8 inset}}
.event.current .date{{color:#355b1f}}
.event.current .title::after{{content:"aktuelt";display:inline-block;margin-left:7px;padding:1px 7px;border-radius:999px;background:#e4f2dc;border:1px solid #bed6b4;color:#275d38;font-size:11px;font-weight:800;vertical-align:middle;white-space:nowrap}}
@media print{{.event.current{{box-shadow:none;border-width:2px}}}}
{CSS_END}"""

JS_BLOCK = f"""{JS_START}
<script>
(() => {{
  const monthMap = new Map(Object.entries({{
    jan: 0, januar: 0,
    feb: 1, februar: 1,
    mar: 2, marts: 2,
    apr: 3, april: 3,
    may: 4, maj: 4,
    jun: 5, juni: 5,
    jul: 6, juli: 6,
    aug: 7, august: 7,
    sep: 8, sept: 8, september: 8,
    oct: 9, okt: 9, oktober: 9,
    nov: 10, november: 10,
    dec: 11, december: 11,
  }}));

  const normalise = (value) => new Date(value.getFullYear(), value.getMonth(), value.getDate());
  const formatLocalIso = (value) => {{
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${{year}}-${{month}}-${{day}}`;
  }};

  function parseStartYear() {{
    const meta = document.querySelector(".meta")?.textContent || "";
    const match = meta.match(/Oversigt:\s*\d{{1,2}}-\d{{1,2}}-(\d{{4}})/i);
    return match ? Number(match[1]) : new Date().getFullYear();
  }}

  function parseDatePart(text, year, fallbackMonth = undefined) {{
    const match = text.trim().replace(/\s+/g, " ").match(/(\d{{1,2}})\.\s*([A-Za-zÆØÅæøå.]+)?/);
    if (!match) return null;
    const day = Number(match[1]);
    const rawMonth = (match[2] || "").replace(/\./g, "").toLowerCase();
    let month = rawMonth ? monthMap.get(rawMonth) : fallbackMonth;
    if (month === undefined && rawMonth.length >= 3) {{
      month = monthMap.get(rawMonth.slice(0, 3));
    }}
    if (month === undefined || Number.isNaN(day)) return null;
    return new Date(year, month, day);
  }}

  function parseRange(text, year) {{
    const parts = text.split(/[–-]/).map((part) => part.trim()).filter(Boolean);
    if (!parts.length) return null;
    const start = parseDatePart(parts[0], year);
    if (!start) return null;
    let end = parts.length > 1 ? parseDatePart(parts[parts.length - 1], year, start.getMonth()) : null;
    if (!end) end = new Date(start);
    if (end < start) end.setFullYear(end.getFullYear() + 1);
    return [normalise(start), normalise(end)];
  }}

  const today = normalise(new Date());
  const initialYear = parseStartYear();
  document.querySelectorAll(".bed").forEach((section) => {{
    let currentYear = initialYear;
    Array.from(section.children).forEach((node) => {{
      if (node.classList?.contains("year-divider")) {{
        const yearText = node.querySelector("span")?.textContent || "";
        const year = Number(yearText.trim());
        if (!Number.isNaN(year)) currentYear = year;
        return;
      }}
      if (!node.classList?.contains("event")) return;
      const dateText = node.querySelector(".date")?.textContent || "";
      const range = parseRange(dateText, currentYear);
      if (!range) return;
      const [start, end] = range;
      node.dataset.start = formatLocalIso(start);
      node.dataset.end = formatLocalIso(end);
      node.classList.toggle("current", today >= start && today <= end);
    }});
  }});
}})();
</script>
{JS_END}"""


def strip_between(text: str, start: str, end: str) -> str:
    while start in text and end in text:
        before, rest = text.split(start, 1)
        _removed, after = rest.split(end, 1)
        text = before + after
    return text


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    html = strip_between(html, CSS_START, CSS_END)
    html = strip_between(html, JS_START, JS_END)

    if "</style>" not in html:
        raise SystemExit("index.html mangler </style>")
    if "</body>" not in html:
        raise SystemExit("index.html mangler </body>")

    html = html.replace("</style>", CSS_BLOCK + "</style>", 1)
    html = html.replace("</body>", JS_BLOCK + "</body>", 1)
    HTML_PATH.write_text(html, encoding="utf-8")
    print("Tilføjede dynamisk highlight af aktuelle overview-events.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
