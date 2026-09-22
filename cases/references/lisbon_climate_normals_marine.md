# get_climate_normals(38.7106, -9.1378, include_marine=true)

Stored verbatim as the agent's own tool returns it. Waves and wind are the
part no other climate source in the agent carries: `get_region_climate`
reads a Wikipedia climate table, which has temperature and precipitation
and no marine data at all.

```json
{
  "mode": "climate_normals",
  "source_years": "2023–2025",
  "note": "Monthly averages from 3 years of historical data. Temperatures in °C, precipitation in mm/day, wind in km/h, waves in m/s.",
  "months": [
    {
      "month": 1,
      "month_name": "Jan",
      "avg_temp_max_c": 15.7,
      "avg_temp_min_c": 9.9,
      "avg_daily_precip_mm": 3.6,
      "avg_max_wind_kmh": 19.5,
      "avg_wave_height_max_m": 1.8,
      "avg_wave_period_max_s": 11.8
    },
    {
      "month": 2,
      "month_name": "Feb",
      "avg_temp_max_c": 16.5,
      "avg_temp_min_c": 9.8,
      "avg_daily_precip_mm": 2.4,
      "avg_max_wind_kmh": 18.1,
      "avg_wave_height_max_m": 1.6,
      "avg_wave_period_max_s": 12.2
    },
    {
      "month": 3,
      "month_name": "Mar",
      "avg_temp_max_c": 17.5,
      "avg_temp_min_c": 10.4,
      "avg_daily_precip_mm": 3.2,
      "avg_max_wind_kmh": 20.7,
      "avg_wave_height_max_m": 1.9,
      "avg_wave_period_max_s": 11.6
    },
    {
      "month": 4,
      "month_name": "Apr",
      "avg_temp_max_c": 21.5,
      "avg_temp_min_c": 12.8,
      "avg_daily_precip_mm": 1.7,
      "avg_max_wind_kmh": 19.5,
      "avg_wave_height_max_m": 1.3,
      "avg_wave_period_max_s": 10
    },
    {
      "month": 5,
      "month_name": "May",
      "avg_temp_max_c": 23.4,
      "avg_temp_min_c": 14.4,
      "avg_daily_precip_mm": 0.6,
      "avg_max_wind_kmh": 20.3,
      "avg_wave_height_max_m": 0.9,
      "avg_wave_period_max_s": 8.5
    },
    {
      "month": 6,
      "month_name": "Jun",
      "avg_temp_max_c": 26.8,
      "avg_temp_min_c": 17.1,
      "avg_daily_precip_mm": 0.8,
      "avg_max_wind_kmh": 19.3,
      "avg_wave_height_max_m": 0.8,
      "avg_wave_period_max_s": 7.9
    },
    {
      "month": 7,
      "month_name": "Jul",
      "avg_temp_max_c": 28.9,
      "avg_temp_min_c": 18.2,
      "avg_daily_precip_mm": 0.2,
      "avg_max_wind_kmh": 19.9,
      "avg_wave_height_max_m": 0.7,
      "avg_wave_period_max_s": 7.4
    },
    {
      "month": 8,
      "month_name": "Aug",
      "avg_temp_max_c": 30.1,
      "avg_temp_min_c": 18.9,
      "avg_daily_precip_mm": 0,
      "avg_max_wind_kmh": 20.5,
      "avg_wave_height_max_m": 0.8,
      "avg_wave_period_max_s": 8.3
    },
    {
      "month": 9,
      "month_name": "Sep",
      "avg_temp_max_c": 26.3,
      "avg_temp_min_c": 16.9,
      "avg_daily_precip_mm": 1,
      "avg_max_wind_kmh": 19.3,
      "avg_wave_height_max_m": 1,
      "avg_wave_period_max_s": 9.4
    },
    {
      "month": 10,
      "month_name": "Oct",
      "avg_temp_max_c": 23.8,
      "avg_temp_min_c": 16.4,
      "avg_daily_precip_mm": 3.1,
      "avg_max_wind_kmh": 19,
      "avg_wave_height_max_m": 1.4,
      "avg_wave_period_max_s": 10.2
    },
    {
      "month": 11,
      "month_name": "Nov",
      "avg_temp_max_c": 18.8,
      "avg_temp_min_c": 12.8,
      "avg_daily_precip_mm": 3.7,
      "avg_max_wind_kmh": 17.7,
      "avg_wave_height_max_m": 1.5,
      "avg_wave_period_max_s": 10.8
    },
    {
      "month": 12,
      "month_name": "Dec",
      "avg_temp_max_c": 15.3,
      "avg_temp_min_c": 9.5,
      "avg_daily_precip_mm": 2,
      "avg_max_wind_kmh": 17.2,
      "avg_wave_height_max_m": 1.4,
      "avg_wave_period_max_s": 11.8
    }
  ]
}
```
