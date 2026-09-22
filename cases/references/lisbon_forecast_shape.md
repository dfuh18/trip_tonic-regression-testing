# get_weather(38.7071, -9.1358, <today>, <today+3>)

**The values here are not the reference and must not be scored against.**
A forecast is true for the day it was fetched and for no other, and D23
settles that a stored forecast cannot be a reference for a run made later.
What this file documents is the **shape** the tool returns, so a reader can
tell what the reply had available to it: `mode: forecast`, a timezone, and
one object per day carrying min and max temperature, precipitation in mm
and as a probability, maximum wind, UV index and a conditions phrase.

The case's criteria are written against that shape — day by day, named as a
forecast rather than an average — and not against any number below. The
assertion that the forecast path *works* is structural, not scored:
`tools_any_of: [get_weather]` with `tool_errors: none`.

Captured 2026-09-22 by calling the tool's own
`getWeatherForecast` directly.

```json
{
  "mode": "forecast",
  "timezone": "Europe/Lisbon",
  "days": [
    {
      "date": "2026-09-22",
      "temp_min_c": 21.6,
      "temp_max_c": 31.5,
      "precipitation_mm": 0,
      "precipitation_probability_pct": 0,
      "wind_speed_max_kmh": 13,
      "uv_index_max": 6.35,
      "conditions": "Clear sky"
    },
    {
      "date": "2026-09-23",
      "temp_min_c": 21,
      "temp_max_c": 32.6,
      "precipitation_mm": 0,
      "precipitation_probability_pct": 0,
      "wind_speed_max_kmh": 13.6,
      "uv_index_max": 6.25,
      "conditions": "Partly cloudy"
    },
    {
      "date": "2026-09-24",
      "temp_min_c": 19.5,
      "temp_max_c": 33.2,
      "precipitation_mm": 0,
      "precipitation_probability_pct": 0,
      "wind_speed_max_kmh": 13.2,
      "uv_index_max": 6.2,
      "conditions": "Clear sky"
    },
    {
      "date": "2026-09-25",
      "temp_min_c": 18.6,
      "temp_max_c": 32,
      "precipitation_mm": 0,
      "precipitation_probability_pct": 0,
      "wind_speed_max_kmh": 10,
      "uv_index_max": 6,
      "conditions": "Overcast"
    }
  ]
}
```
