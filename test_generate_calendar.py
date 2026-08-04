from datetime import date
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import generate_calendar


class WeatherForecastTest(TestCase):
    def test_daily_hourly_minimum_groups_local_timestamps(self) -> None:
        result = generate_calendar.daily_hourly_minimum(
            {
                "time": [
                    "2026-08-04T00:00",
                    "2026-08-04T06:00",
                    "2026-08-05T00:00",
                    "2026-08-05T06:00",
                ],
                "soil_temperature_6cm": [11.2, 9.4, None, 10.1],
            },
            "soil_temperature_6cm",
        )

        self.assertEqual(
            result,
            {date(2026, 8, 4): 9.4, date(2026, 8, 5): 10.1},
        )

    @patch("generate_calendar.resolve_coordinates", return_value=(55.4, 10.2, "5485"))
    @patch("generate_calendar.request_json")
    def test_load_weather_requests_hourly_soil_temperature(
        self, request_json, _resolve_coordinates
    ) -> None:
        request_json.return_value = {
            "daily": {
                "time": ["2026-08-04", "2026-08-05"],
                "temperature_2m_min": [12.0, 13.0],
                "precipitation_sum": [0.2, 1.0],
                "precipitation_probability_max": [15, 30],
                "et0_fao_evapotranspiration": [3.1, 2.8],
            },
            "hourly": {
                "time": [
                    "2026-08-04T00:00",
                    "2026-08-04T12:00",
                    "2026-08-05T00:00",
                    "2026-08-05T12:00",
                ],
                "soil_temperature_6cm": [6.5, 14.0, 11.0, 15.0],
            },
        }
        config = {
            "project": {"timezone": "Europe/Copenhagen"},
            "weather": {"enabled": True, "postal_code": "5485"},
        }

        result = generate_calendar.load_weather(config, date(2026, 8, 4))

        query = parse_qs(urlparse(request_json.call_args.args[0]).query)
        self.assertEqual(query["hourly"], ["soil_temperature_6cm"])
        self.assertNotIn("soil_temperature_6cm_min", query["daily"][0])
        self.assertEqual(result[date(2026, 8, 4)]["soil_temperature_6cm_min"], 6.5)
        self.assertEqual(result[date(2026, 8, 5)]["soil_temperature_6cm_min"], 11.0)

        actual_day, weather_note = generate_calendar.adjust_for_weather(
            {"action": "Så", "crop": "majs", "location": "Bed 2"},
            date(2026, 8, 4),
            date(2026, 8, 4),
            result,
            {"postal_code": "5485", "warm_crop_soil_min_temperature_c": 8},
        )
        self.assertEqual(actual_day, date(2026, 8, 5))
        self.assertIn("Flyttet fra 04-08 til 05-08", weather_note or "")
