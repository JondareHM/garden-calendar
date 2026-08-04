#!/usr/bin/env python3
"""Generate a weather-aware, YAML-driven garden subscription calendar."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, NoReturn
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "garden.yaml"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"Fejl: {message}")


def warn(message: str) -> None:
    print(f"Advarsel: {message}", file=sys.stderr)


def parse_month_day(value: str, year: int) -> date:
    try:
        month, day = (int(part) for part in value.split("-", 1))
        return date(year, month, day)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Ugyldig dato '{value}' for år {year}") from exc


def add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # 29 February becomes 28 February in a non-leap year.
        return value.replace(year=value.year + years, day=28)


def subtract_month(value: date) -> date:
    year = value.year
    month = value.month - 1
    if month == 0:
        year -= 1
        month = 12
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def generation_date(config: dict[str, Any]) -> date:
    override = os.environ.get("GARDEN_CALENDAR_DATE")
    if override:
        try:
            return date.fromisoformat(override)
        except ValueError as exc:
            raise ValueError("GARDEN_CALENDAR_DATE skal være YYYY-MM-DD") from exc

    timezone_name = str(config.get("project", {}).get("timezone", "Europe/Copenhagen"))
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except (KeyError, ValueError):
        return date.today()


def generation_window(config: dict[str, Any], generated_on: date) -> tuple[date, date]:
    months_before = int(config.get("project", {}).get("generation_months_before", 1))
    if months_before < 0:
        fail("generation_months_before må ikke være negativ")
    start = generated_on
    for _ in range(months_before):
        start = subtract_month(start)
    return start, add_years(start, 1)


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


def enabled(event: dict[str, Any], config: dict[str, Any]) -> bool:
    required_mode = event.get("mode")
    if required_mode and required_mode != config.get("bed4_mode", "leeks"):
        return False
    enabled_by = event.get("enabled_by")
    if enabled_by and not bool(config.get(str(enabled_by), False)):
        return False
    return bool(event.get("enabled", True))


def make_uid(calendar_id: str, event_id: str, planned_day: date, occurrence: int) -> str:
    """Keep the UID tied to the original plan date, not a weather-shifted date."""
    raw = f"{calendar_id}:{event_id}:{planned_day.isoformat()}:{occurrence}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{digest}@havekalender.local"


def make_event_lines(
    calendar_id: str,
    event: dict[str, Any],
    event_day: date,
    planned_day: date,
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
    description_lines = [
        f"Handling: {event.get('action', 'Opgave')}",
        f"Afgrøde: {crop or 'Ikke angivet'}",
        f"Placering: {event.get('location', 'Hele haven')}",
        f"Note: {event.get('note', '')}",
    ]
    weather_note = event.get("_weather_note")
    if weather_note:
        description_lines.append(f"Vejrtilpasning: {weather_note}")
    description = "\n".join(description_lines)
    category = event.get("category", "Have")
    return [
        "BEGIN:VEVENT",
        f"UID:{make_uid(calendar_id, str(event['id']), planned_day, occurrence)}",
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


def request_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "havekalender/1.0"})
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("API-svaret er ikke et JSON-objekt")
    if payload.get("error"):
        raise ValueError(str(payload.get("reason", "ukendt API-fejl")))
    return payload


def weather_settings(config: dict[str, Any]) -> dict[str, Any]:
    settings = config.get("weather", {})
    if settings is None:
        return {}
    if not isinstance(settings, dict):
        fail("weather skal være et YAML-objekt")
    return settings


def resolve_coordinates(settings: dict[str, Any]) -> tuple[float, float, str]:
    latitude = settings.get("latitude")
    longitude = settings.get("longitude")
    if latitude is not None and longitude is not None:
        return float(latitude), float(longitude), str(settings.get("postal_code", "konfigureret lokation"))

    postal_code = str(settings.get("postal_code", "")).strip()
    if not postal_code:
        raise ValueError("weather.postal_code mangler")
    params = {
        "name": postal_code,
        "count": 10,
        "language": "da",
        "format": "json",
        "countryCode": str(settings.get("country_code", "DK")),
    }
    data = request_json("https://geocoding-api.open-meteo.com/v1/search?" + urlencode(params))
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError(f"postnummer {postal_code} kunne ikke geokodes")

    selected = results[0]
    for result in results:
        if postal_code in {str(item) for item in result.get("postcodes", [])}:
            selected = result
            break
    return float(selected["latitude"]), float(selected["longitude"]), postal_code


def load_weather(config: dict[str, Any], generated_on: date) -> dict[date, dict[str, float | None]]:
    settings = weather_settings(config)
    if not bool(settings.get("enabled", False)):
        return {}
    if os.environ.get("GARDEN_CALENDAR_DISABLE_WEATHER") == "1":
        print("Vejrtilpasning deaktiveret via GARDEN_CALENDAR_DISABLE_WEATHER.")
        return {}

    try:
        latitude, longitude, location_label = resolve_coordinates(settings)
        forecast_days = max(1, min(16, int(settings.get("forecast_days", 16))))
        past_days = max(0, min(7, int(settings.get("past_days", 7))))
        timezone_name = str(config.get("project", {}).get("timezone", "Europe/Copenhagen"))
        daily = ",".join(
            [
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "soil_temperature_6cm_min",
                "et0_fao_evapotranspiration",
            ]
        )
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": daily,
            "timezone": timezone_name,
            "forecast_days": forecast_days,
            "past_days": past_days,
        }
        data = request_json("https://api.open-meteo.com/v1/forecast?" + urlencode(params))
        daily_data = data.get("daily")
        if not isinstance(daily_data, dict):
            raise ValueError("forecast-svaret mangler daily-data")
        days = daily_data.get("time")
        if not isinstance(days, list):
            raise ValueError("forecast-svaret mangler datoer")

        result: dict[date, dict[str, float | None]] = {}
        fields = [
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "soil_temperature_6cm_min",
            "et0_fao_evapotranspiration",
        ]
        for index, day_text in enumerate(days):
            values: dict[str, float | None] = {}
            for field in fields:
                field_values = daily_data.get(field, [])
                raw_value = field_values[index] if index < len(field_values) else None
                values[field] = None if raw_value is None else float(raw_value)
            result[date.fromisoformat(str(day_text))] = values
        print(f"Vejrprognose hentet for postnummer {location_label} ({len(result)} dage).")
        return result
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        warn(f"vejrdata kunne ikke hentes ({exc}); bruger faste kalenderdatoer")
        return {}


def weather_mode(event: dict[str, Any]) -> str | None:
    explicit = event.get("weather_mode")
    if explicit:
        return str(explicit)

    action = str(event.get("action", "")).strip().lower()
    crop = str(event.get("crop", "")).lower()
    location = str(event.get("location", "")).lower()

    if action == "plant ud" and "drivhus" in location:
        return "greenhouse_plant"
    if "drivhus" in location or "inde" in location:
        # Rain is not a useful signal for greenhouse sowing or care tasks.
        return None
    if action.startswith("høst"):
        return "harvest"
    if "så" in action:
        return "outdoor_sow"
    if action in {"plant ud", "sæt"}:
        return "outdoor_plant"
    return None


def number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def weather_values(event: dict[str, Any], values: dict[str, float | None], settings: dict[str, Any]) -> tuple[bool, float]:
    mode = weather_mode(event)
    minimum_temperature = number(values.get("temperature_2m_min"), 99)
    soil_temperature = number(values.get("soil_temperature_6cm_min"), 99)
    rain = number(values.get("precipitation_sum"), 0)
    rain_probability = number(values.get("precipitation_probability_max"), 0)
    rain_limit = number(settings.get("rain_mm", 8), 8)
    rain_probability_limit = number(settings.get("rain_probability_percent", 70), 70)
    heavy_rain_probability = number(settings.get("heavy_rain_probability_mm", 4), 4)

    if mode == "greenhouse_plant":
        threshold = number(settings.get("greenhouse_min_temperature_c", 5), 5)
        return minimum_temperature >= threshold, max(0, threshold - minimum_temperature) * 10

    if mode == "outdoor_sow":
        crop = str(event.get("crop", "")).lower()
        soil_limit = number(settings.get("soil_min_temperature_c", 4), 4)
        if any(name in crop for name in ("majs", "buskbønner", "rødbeder")):
            soil_limit = number(settings.get("warm_crop_soil_min_temperature_c", 8), 8)
        temperature_penalty = max(0, soil_limit - soil_temperature)
        rain_penalty = max(0, rain - rain_limit)
        likely_wet = rain >= heavy_rain_probability and rain_probability >= rain_probability_limit
        return temperature_penalty == 0 and rain < rain_limit and not likely_wet, temperature_penalty * 5 + rain_penalty * 2

    if mode == "outdoor_plant":
        threshold = number(settings.get("outdoor_min_temperature_c", 3), 3)
        temperature_penalty = max(0, threshold - minimum_temperature)
        rain_penalty = max(0, rain - rain_limit)
        likely_wet = rain >= heavy_rain_probability and rain_probability >= rain_probability_limit
        return minimum_temperature >= threshold and rain < rain_limit and not likely_wet, temperature_penalty * 10 + rain_penalty * 2

    if mode == "harvest":
        harvest_rain_limit = number(settings.get("harvest_rain_mm", 10), 10)
        likely_wet = rain >= heavy_rain_probability and rain_probability >= rain_probability_limit
        frost_penalty = max(0, -1 - minimum_temperature)
        rain_penalty = max(0, rain - harvest_rain_limit)
        return minimum_temperature > -1 and rain < harvest_rain_limit and not likely_wet, frost_penalty * 5 + rain_penalty

    return True, 0


def adjust_for_weather(
    event: dict[str, Any],
    planned_day: date,
    generated_on: date,
    forecast: dict[date, dict[str, float | None]],
    settings: dict[str, Any],
) -> tuple[date, str | None]:
    mode = weather_mode(event)
    if not mode or planned_day < generated_on or planned_day not in forecast:
        return planned_day, None

    max_shift = max(0, min(7, int(settings.get("max_shift_days", 5))))
    available_days = sorted(day for day in forecast if day >= planned_day)
    if not available_days:
        return planned_day, None
    last_day = min(planned_day + timedelta(days=max_shift), available_days[-1])
    candidates = [day for day in available_days if planned_day <= day <= last_day]
    if not candidates:
        return planned_day, None

    planned_good, planned_penalty = weather_values(event, forecast[planned_day], settings)
    if planned_good:
        return planned_day, None

    for candidate in candidates[1:]:
        good, _ = weather_values(event, forecast[candidate], settings)
        if good:
            location = str(settings.get("postal_code", "haven"))
            note = f"Flyttet fra {planned_day:%d-%m} til {candidate:%d-%m} ud fra vejrprognosen for postnummer {location}."
            return candidate, note

    best_day = min(candidates, key=lambda day: weather_values(event, forecast[day], settings)[1])
    if best_day != planned_day and weather_values(event, forecast[best_day], settings)[1] < planned_penalty:
        location = str(settings.get("postal_code", "haven"))
        note = f"Flyttet fra {planned_day:%d-%m} til {best_day:%d-%m} ud fra vejrprognosen for postnummer {location}."
        return best_day, note
    return planned_day, None


def extra_outdoor_watering_events(
    forecast: dict[date, dict[str, float | None]],
    generated_on: date,
    settings: dict[str, Any],
) -> list[tuple[dict[str, Any], date, date, int]]:
    """Create at most one reminder per consecutive dry period for outdoor beds."""
    if not bool(settings.get("extra_outdoor_watering", True)):
        return []
    if bool(settings.get("greenhouse_extra_watering", False)):
        warn("greenhouse_extra_watering ignoreres; drivhuset får ingen regnbaseret vanding")

    lookback_days = max(2, min(7, int(settings.get("watering_lookback_days", 5))))
    rain_limit = number(settings.get("watering_rain_max_mm", 4), 4)
    et0_limit = number(settings.get("watering_et0_min_mm", 10), 10)
    forecast_days = max(1, min(16, int(settings.get("forecast_days", 16))))
    last_day = generated_on + timedelta(days=forecast_days - 1)
    result: list[tuple[dict[str, Any], date, date, int]] = []
    dry_period = False

    for day in sorted(forecast):
        if day < generated_on or day > last_day:
            continue
        window = [forecast.get(day - timedelta(days=offset)) for offset in range(lookback_days)]
        if any(values is None for values in window):
            continue
        rain_total = sum(number(values.get("precipitation_sum"), 0) for values in window if values)
        et0_total = sum(number(values.get("et0_fao_evapotranspiration"), 0) for values in window if values)
        is_dry = rain_total <= rain_limit and et0_total >= et0_limit
        if is_dry and not dry_period:
            event = {
                "id": f"extra_outdoor_watering_{day.isoformat()}",
                "emoji": "💧",
                "action": "Vand grundigt",
                "crop": "udendørs bede",
                "location": "Udendørs bede",
                "note": "Vejrbaseret ekstra påmindelse ved flere tørre dage. Kontrollér altid jorden først. Dette gælder ikke drivhusets kapillærkasser.",
                "category": "Vanding",
            }
            result.append((event, day, day, 1))
        dry_period = is_dry
    return result


def current_dtstamp(config: dict[str, Any]) -> str:
    configured = config.get("project", {}).get("dtstamp")
    if configured and str(configured).lower() != "dynamic":
        return str(configured)
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def generate(config: dict[str, Any]) -> str:
    project = config.get("project", {})
    calendar_id = str(project.get("id", "havekalender"))
    alarm_days = int(project.get("alarm_days_before", 2))
    if alarm_days < 0:
        fail("alarm_days_before må ikke være negativ")
    dtstamp = current_dtstamp(config)
    timezone_name = str(project.get("timezone", "Europe/Copenhagen"))
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

    generated_on = generation_date(config)
    window_start, window_end = generation_window(config, generated_on)
    settings = weather_settings(config)
    forecast = load_weather(config, generated_on)

    instances: list[tuple[dict[str, Any], date, date, int]] = []
    seen_ids: set[str] = set()
    year_start = window_start.year
    year_end = window_end.year
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
        for year in range(year_start, year_end + 1):
            for planned_day, occurrence in event_dates(event, year):
                if planned_day < window_start or planned_day >= window_end:
                    continue
                actual_day, weather_note = adjust_for_weather(
                    event, planned_day, generated_on, forecast, settings
                )
                output_event = dict(event)
                if weather_note:
                    output_event["_weather_note"] = weather_note
                instances.append((output_event, actual_day, planned_day, occurrence))

    instances.extend(extra_outdoor_watering_events(forecast, generated_on, settings))
    instances.sort(key=lambda item: (item[1], event_summary(item[0]), item[0]["id"]))

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//JondareHM//Havekalender//DA",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(calendar_name)}",
        f"X-WR-CALDESC:{escape_text(description)}",
        f"X-WR-TIMEZONE:{escape_text(timezone_name)}",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for event, actual_day, planned_day, occurrence in instances:
        lines.extend(
            make_event_lines(
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
    result = ical_lines(lines)
    print(
        f"Genererede {len(instances)} kalenderbegivenheder for {calendar_name} "
        f"({window_start:%Y-%m-%d} til {(window_end - timedelta(days=1)):%Y-%m-%d})."
    )
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
