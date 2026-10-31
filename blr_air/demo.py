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
                )
            )
        return Forecast(
            tuple(rows),
            CurrentAir(start, rows[0].us_aqi, rows[0].pm2_5),
            "Asia/Kolkata",
            now,
            is_demo=True,
        )
