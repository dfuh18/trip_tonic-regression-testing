<!-- source: Open-Meteo archive API
     tool: get_climate_normals({ lat: 38.7434, lng: -9.1604 }) --
     apps/api/src/routes/ai/lib/weather.ts. The coordinates are the centre of the fixture
     trip's Lisbon bounding box, which is what get_trip_details hands the agent.
     Three complete calendar years, so these figures are stable until 2027-01-01.
     retrieved: 2026-09-19 -->

```json
{
  "mode": "climate_normals",
  "source_years": "2023–2025",
  "note": "Monthly averages from 3 years of historical data. Temperatures in °C, precipitation in mm/day, wind in km/h, waves in m/s.",
  "months": [
    {
      "month": 1,
      "month_name": "Jan",
      "avg_temp_max_c": 15.2,
      "avg_temp_min_c": 9.5,
      "avg_daily_precip_mm": 4.1,
      "avg_max_wind_kmh": 18.8
    },
    {
      "month": 2,
      "month_name": "Feb",
      "avg_temp_max_c": 16.1,
      "avg_temp_min_c": 9.5,
      "avg_daily_precip_mm": 2.8,
      "avg_max_wind_kmh": 18.1
    },
    {
      "month": 3,
      "month_name": "Mar",
      "avg_temp_max_c": 17.1,
      "avg_temp_min_c": 10.2,
      "avg_daily_precip_mm": 3.6,
      "avg_max_wind_kmh": 20.3
    },
    {
      "month": 4,
      "month_name": "Apr",
      "avg_temp_max_c": 21.4,
      "avg_temp_min_c": 12.5,
      "avg_daily_precip_mm": 1.8,
      "avg_max_wind_kmh": 20.1
    },
    {
      "month": 5,
      "month_name": "May",
      "avg_temp_max_c": 23,
      "avg_temp_min_c": 13.9,
      "avg_daily_precip_mm": 0.9,
      "avg_max_wind_kmh": 20.9
    },
    {
      "month": 6,
      "month_name": "Jun",
      "avg_temp_max_c": 26.3,
      "avg_temp_min_c": 16.6,
      "avg_daily_precip_mm": 1.1,
      "avg_max_wind_kmh": 20.4
    },
    {
      "month": 7,
      "month_name": "Jul",
      "avg_temp_max_c": 28.4,
      "avg_temp_min_c": 17.6,
      "avg_daily_precip_mm": 0.1,
      "avg_max_wind_kmh": 22.2
    },
    {
      "month": 8,
      "month_name": "Aug",
      "avg_temp_max_c": 29.8,
      "avg_temp_min_c": 18.5,
      "avg_daily_precip_mm": 0,
      "avg_max_wind_kmh": 22.7
    },
    {
      "month": 9,
      "month_name": "Sep",
      "avg_temp_max_c": 25.9,
      "avg_temp_min_c": 16.6,
      "avg_daily_precip_mm": 1,
      "avg_max_wind_kmh": 20.1
    },
    {
      "month": 10,
      "month_name": "Oct",
      "avg_temp_max_c": 23.5,
      "avg_temp_min_c": 16.3,
      "avg_daily_precip_mm": 3.4,
      "avg_max_wind_kmh": 18.8
    },
    {
      "month": 11,
      "month_name": "Nov",
      "avg_temp_max_c": 18.3,
      "avg_temp_min_c": 12.4,
      "avg_daily_precip_mm": 3.7,
      "avg_max_wind_kmh": 17.5
    },
    {
      "month": 12,
      "month_name": "Dec",
      "avg_temp_max_c": 14.8,
      "avg_temp_min_c": 9.1,
      "avg_daily_precip_mm": 2,
      "avg_max_wind_kmh": 16.8
    }
  ]
}
```
