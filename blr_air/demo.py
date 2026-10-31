from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from blr_air.domain import CurrentAir, Forecast, Hour, LocationError
from blr_air.localities import local_location


class DemoProvider:
    """Synthetic offline dataset for testing the full recommendation path."""

    async def locate(self, place):
        result = local_location(place)
        if result is None:
            raise LocationError("The offline demo supports Bengaluru localities only.")
        return result

    async def forecast(self, location):
        now = datetime.now(UTC)
        start = now.astimezone(ZoneInfo("Asia/Kolkata")).replace(minute=0, second=0, microsecond=0)
        rows = []
        for i in range(72):
            time = (start + timedelta(hours=i)).astimezone(UTC)
            local_hour = time.astimezone(ZoneInfo("Asia/Kolkata")).hour
            rows.append(
                Hour(
                    time,
                    45 + abs(local_hour - 9) * 5,
                    12 + abs(local_hour - 9),
                    10 if local_hour < 14 else 65,
                    24 + max(0, 5 - abs(local_hour - 14)),
                    apparent_temperature=26 + max(0, 5 - abs(local_hour - 14)),
                    uv_index=max(0, 8 - 2 * abs(local_hour - 12)),
                    wind_speed=8,
                )
            )
        return Forecast(
            tuple(rows),
            CurrentAir(start, rows[0].us_aqi, rows[0].pm2_5),
            "Asia/Kolkata",
            now,
            is_demo=True,
            daylight=tuple(
                (
                    (start + timedelta(days=day)).replace(hour=6).astimezone(UTC),
                    (start + timedelta(days=day)).replace(hour=18).astimezone(UTC),
                )
                for day in range(4)
            ),
        )
