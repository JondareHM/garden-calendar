#!/usr/bin/env python3
"""Generate a personal, YAML-driven garden subscription calendar."""

from __future__ import annotations

import hashlib
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, NoReturn

import yaml


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "garden.yaml"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"Fejl: {message}")


def parse_month_day(value: str, year: int) -> date:
    try:
        month, day = (int(part) for part in value.split("-", 1))
        return date(year, month, day)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Ugyldig dato '{value}' for år {year}") from exc


def escape_text(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold_ical_line(line: str) -> list[str]:
    """Fold an iCalendar line without splitting UTF-8 characters."""
    result: list[str] = []
    remaining = line
    first = True
    while remaining:
        limit = 75 if first else 74
        chunk = ""
        for character in remaining:
            candidate = chunk + character
            if len(candidate.encode("utf-8")) > limit:
                break
            chunk = candidate
        if not chunk:
            raise ValueError("Kunne ikke folde iCalendar-linje")
        result.append(chunk if first else f" {chunk}")
        remaining = remaining[len(chunk) :]
        first = False
    return result or [""]


def ical_lines(lines: Iterable[str]) -> str:
    folded: list[str] = []
    for line in lines:
        folded.extend(fold_ical_line(line))
    return "\r\n".join(folded) + "\r\n"


def event_summary(event: dict[str, Any]) -> str:
    parts = [event.get("action", "Opgave")]
    crop = event.get("crop")
    location = event.get("location")
    if crop:
        parts.append(str(crop))
    summary = " ".join(str(part) for part in parts)
    if location:
        summary += f" – {location}"
    emoji = event.get("emoji", "🌱")
    return f"{emoji} {summary}"


def event_dates(event: dict[str, Any], year: int) -> list[tuple[date, int]]:
    start = parse_month_day(str(event["start"]), year)
    end = parse_month_day(str(event.get("end", event["start"])), year)
    if end < start:
        raise ValueError(f"Slutdato ligger før startdato for '{event.get('id', '?')}'")

    repeat_days = event.get("repeat_days")
    if repeat_days in (None, "", 0):
        return [(start, 1)]
    try:
        repeat_days = int(repeat_days)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"repeat_days skal være et heltal for '{event.get('id', '?')}'") from exc
    if repeat_days < 1:
        raise ValueError(f"repeat_days skal være større end 0 for '{event.get('id', '?')}'")

    dates: list[tuple[date, int]] = []
    current = start
    occurrence = 1
    while current <= end:
        dates.append((current, occurrence))
        current += timedelta(days=repeat_days)
        occurrence += 1
    return dates


def years_to_generate(config: dict[str, Any]) -> range:
    first_year = int(config.get("first_year", 2026))
    years_ahead = int(config.get("years_ahead", 10))
    if years_ahead < 1:
        fail("years_ahead skal være mindst 1")
    first_active_year = max(first_year, date.today().year)
    return range(first_active_year, first_active_year + years_ahead)


def enabled(event: dict[str, Any], config: dict[str, Any]) -> bool:
    required_mode = event.get("mode")
    if required_mode and required_mode != config.get("bed4_mode", "leeks"):
        return False
    enabled_by = event.get("enabled_by")
    if enabled_by and not bool(config.get(str(enabled_by), False)):
        return False
    return bool(event.get("enabled", True))


def make_uid(calendar_id: str, event_id: str, event_day: date, occurrence: int) -> str:
    raw = f"{calendar_id}:{event_id}:{event_day.isoformat()}:{occurrence}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{digest}@havekalender.local"


def make_event_lines(
    calendar_id: str,
    event: dict[str, Any],
    event_day: date,
    occurrence: int,
    alarm_days: int,
    dtstamp: str,
) -> list[str]:
    summary = event_summary(event)
    duration_days = int(event.get("duration_days", 1))
    if duration_days < 1:
        raise ValueError(f"duration_days skal være mindst 1 for '{event.get('id', '?')}'")
    end_day = event_day + timedelta(days=duration_days)
    crop = event.get("crop", "")
    description = "\n".join(
        [
            f"Handling: {event.get('action', 'Opgave')}",
            f"Afgrøde: {crop or 'Ikke angivet'}",
            f"Placering: {event.get('location', 'Hele haven')}",
            f"Note: {event.get('note', '')}",
        ]
    )
    category = event.get("category", "Have")
    return [
        "BEGIN:VEVENT",
        f"UID:{make_uid(calendar_id, str(event['id']), event_day, occurrence)}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{event_day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{end_day:%Y%m%d}",
        f"SUMMARY:{escape_text(summary)}",
        f"DESCRIPTION:{escape_text(description)}",
        f"LOCATION:{escape_text(str(event.get('location', 'Hele haven')))}",
        f"CATEGORIES:{escape_text(str(category))}",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
        "SEQUENCE:0",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escape_text(summary)}",
        f"TRIGGER:-P{alarm_days}D",
        "END:VALARM",
        "END:VEVENT",
    ]


def generate(config: dict[str, Any]) -> str:
    project = config.get("project", {})
    calendar_id = str(project.get("id", "havekalender"))
    alarm_days = int(project.get("alarm_days_before", 2))
    if alarm_days < 0:
        fail("alarm_days_before må ikke være negativ")
    dtstamp = str(project.get("dtstamp", "20260101T000000Z"))
    timezone = str(project.get("timezone", "Europe/Copenhagen"))
    calendar_name = str(project.get("calendar_name", "Havekalender"))
    description = str(project.get("description", "Personlig så- og havekalender"))

    events = config.get("events", [])
    if not isinstance(events, list):
        fail("events skal være en liste")

    selected_event_ids = config.get("selected_event_ids")
    if selected_event_ids is not None:
        if not isinstance(selected_event_ids, list):
            fail("selected_event_ids skal være en liste")
        selected_event_ids = {str(event_id) for event_id in selected_event_ids}

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//JondareHM//Havekalender//DA",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(calendar_name)}",
        f"X-WR-CALDESC:{escape_text(description)}",
        f"X-WR-TIMEZONE:{escape_text(timezone)}",
        "X-PUBLISHED-TTL:PT12H",
    ]

    seen_ids: set[str] = set()
    generated_count = 0
    for event in events:
        if not isinstance(event, dict) or "id" not in event or "start" not in event:
            fail("Alle events skal have mindst id og start")
        event_id = str(event["id"])
        if event_id in seen_ids:
            fail(f"Dobbelt event-id: {event_id}")
        seen_ids.add(event_id)
        if selected_event_ids is not None and event_id not in selected_event_ids:
            continue
        if not enabled(event, config):
            continue
        for year in years_to_generate(config):
            for event_day, occurrence in event_dates(event, year):
                lines.extend(make_event_lines(calendar_id, event, event_day, occurrence, alarm_days, dtstamp))
                generated_count += 1

    lines.append("END:VCALENDAR")
    result = ical_lines(lines)
    print(f"Genererede {generated_count} kalenderbegivenheder for {calendar_name}.")
    return result


def main() -> int:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CONFIG_PATH
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        fail("Konfigurationen skal være et YAML-objekt")
    output_path = ROOT / str(config.get("project", {}).get("output", "calendar/have.ics"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate(config), encoding="utf-8", newline="")
    print(f"Skrev {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
