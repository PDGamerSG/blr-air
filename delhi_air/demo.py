from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from delhi_air.domain import CurrentAir, Forecast, Hour, LocationError
from delhi_air.localities import local_location


class DemoProvider:
    """Synthetic offline dataset for testing the full recommendation path."""

    async def locate(self, place):
        result = local_location(place)
        if result is None:
            raise LocationError("The offline demo supports Delhi localities only.")
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
                    # A smoggy Delhi winter day: cleanest mid-afternoon, worst overnight.
                    170 + abs(local_hour - 15) * 6,
                    90 + abs(local_hour - 15) * 7,
                    0 if local_hour < 17 else 15,
                    16 + max(0, 10 - abs(local_hour - 14) * 2),
                    apparent_temperature=15 + max(0, 10 - abs(local_hour - 14) * 2),
                    uv_index=max(0, 5 - abs(local_hour - 12)),
                    wind_speed=6,
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
