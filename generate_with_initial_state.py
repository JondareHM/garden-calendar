#!/usr/bin/env python3
"""Generate calendar and overview with a temporary real-world initial state."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

import generate_calendar as base


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "garden.yaml"
STATE_PATH = ROOT / "initial_state.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        base.fail(f"{path.name} skal være et YAML-objekt")
    return data


def parse_iso_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} skal være YYYY-MM-DD") from exc


def absolute_event_dates(event: dict[str, Any]) -> list[tuple[date, int]]:
    start = parse_iso_date(event.get("start"), f"{event.get('id', '?')}.start")
    end = parse_iso_date(event.get("end", event.get("start")), f"{event.get('id', '?')}.end")
    if end < start:
        raise ValueError(f"Slutdato ligger før startdato for '{event.get('id', '?')}'")

    repeat_days = event.get("repeat_days")
    if repeat_days in (None, "", 0):
        return [(start, 1)]
    repeat_days = int(repeat_days)
    if repeat_days < 1:
        raise ValueError(f"repeat_days skal være større end 0 for '{event.get('id', '?')}'")

    result: list[tuple[date, int]] = []
    current = start
    occurrence = 1
    while current <= end:
        result.append((current, occurrence))
        current += timedelta(days=repeat_days)
        occurrence += 1
    return result


def collect_instances(
    config: dict[str, Any],
    state: dict[str, Any],
    generated_on: date,
    forecast: dict[date, dict[str, float | None]],
) -> tuple[list[tuple[dict[str, Any], date, date, int]], date, date]:
    normal_instances, window_start, window_end = base.collect_instances(config, generated_on, forecast)
    normal_plan_starts = parse_iso_date(state.get("normal_plan_starts"), "normal_plan_starts")

    instances: list[tuple[dict[str, Any], date, date, int]] = []
    for event, actual_day, planned_day, occurrence in normal_instances:
        event_id = str(event.get("id", ""))
        if event_id.startswith("extra_outdoor_watering_") or planned_day >= normal_plan_starts:
            instances.append((event, actual_day, planned_day, occurrence))

    settings = base.weather_settings(config)
    seen_ids: set[str] = set()
    for event in state.get("events", []):
        if not isinstance(event, dict) or "id" not in event or "start" not in event:
            base.fail("Alle initial-state-events skal have mindst id og start")
        event_id = str(event["id"])
        if event_id in seen_ids:
            base.fail(f"Dobbelt initial-state-event-id: {event_id}")
        seen_ids.add(event_id)

        for planned_day, occurrence in absolute_event_dates(event):
            if planned_day < window_start or planned_day >= window_end:
                continue
            if planned_day >= normal_plan_starts:
                continue
            actual_day, weather_note = base.adjust_for_weather(
                event, planned_day, generated_on, forecast, settings
            )
            output_event = dict(event)
            if weather_note:
                output_event["_weather_note"] = weather_note
            instances.append((output_event, actual_day, planned_day, occurrence))

    instances.sort(key=lambda item: (item[1], base.event_summary(item[0]), item[0]["id"]))
    return instances, window_start, window_end


def overview_config(config: dict[str, Any], state: dict[str, Any], generated_on: date) -> dict[str, Any]:
    result = copy.deepcopy(config)
    overview_ids = {str(value) for value in result.get("overview_event_ids", [])}
    for event in state.get("events", []):
        if isinstance(event, dict) and event.get("overview", True):
            overview_ids.add(str(event.get("id")))
    result["overview_event_ids"] = sorted(overview_ids)
    return result


def inject_status(html_text: str, state: dict[str, Any], generated_on: date) -> str:
    # Keep initial_state.yaml as source data for current-year events, but do not
    # show the static status snapshot in the Pages overview.
    return html_text


def build_calendar(
    config: dict[str, Any],
    instances: list[tuple[dict[str, Any], date, date, int]],
) -> str:
    project = config.get("project", {})
    calendar_id = str(project.get("id", "havekalender"))
    alarm_days = int(project.get("alarm_days_before", 2))
    dtstamp = base.current_dtstamp(config)
    timezone_name = str(project.get("timezone", "Europe/Copenhagen"))
    calendar_name = str(project.get("calendar_name", "Havekalender"))
    description = str(project.get("description", "Personlig så- og havekalender"))

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//JondareHM//Havekalender//DA",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{base.escape_text(calendar_name)}",
        f"X-WR-CALDESC:{base.escape_text(description)}",
        f"X-WR-TIMEZONE:{base.escape_text(timezone_name)}",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for event, actual_day, planned_day, occurrence in instances:
        lines.extend(
            base.make_event_lines(
                calendar_id,
                event,
                actual_day,
                planned_day,
                occurrence,
                alarm_days,
                dtstamp,
            )
        )
    lines.append("END:VCALENDAR")
    return base.ical_lines(lines)


def main() -> int:
    config = load_yaml(CONFIG_PATH)
    state = load_yaml(STATE_PATH)
    generated_on = base.generation_date(config)
    forecast = base.load_weather(config, generated_on)
    instances, window_start, window_end = collect_instances(config, state, generated_on, forecast)

    project = config.get("project", {})
    output_path = ROOT / str(project.get("output", "calendar/have.ics"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_calendar(config, instances), encoding="utf-8", newline="")

    display_config = overview_config(config, state, generated_on)
    overview = base.overview_html(display_config, instances, window_start, window_end, generated_on)
    overview = inject_status(overview, state, generated_on)
    overview_path = ROOT / str(project.get("overview_output", "index.html"))
    overview_path.write_text(overview, encoding="utf-8")

    print(
        f"Genererede {len(instances)} begivenheder med initial state "
        f"({window_start:%Y-%m-%d} til {(window_end - timedelta(days=1)):%Y-%m-%d})."
    )
    print(f"Skrev {output_path.relative_to(ROOT)}")
    print(f"Skrev {overview_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
