"""Evidence-based explanations of a forecast, without inventing a venue rating."""

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from blr_air.scoring import aqi_category

if TYPE_CHECKING:
    from blr_air.service import Recommendation


AQI_GUIDANCE = {
    "Good": (
        "Air quality is satisfactory; air pollution poses little or no risk for most people.",
        "Continue to check local conditions and your own response to outdoor activity.",
    ),
    "Moderate": (
        "Air quality is acceptable, but unusually sensitive people may still be affected.",
        "If you are unusually sensitive to air pollution, consider reducing prolonged or "
        "heavy outdoor exertion.",
    ),
    "Unhealthy for sensitive groups": (
        "Sensitive groups may experience health effects; the general public is less likely "
        "to be affected.",
        "Sensitive groups should reduce prolonged or heavy outdoor exertion; consider an "
        "indoor alternative. Follow your clinician's advice for an existing condition.",
    ),
    "Unhealthy": (
        "Everyone may begin to experience health effects; sensitive groups may have "
        "more serious effects.",
        "Reduce prolonged or heavy outdoor exertion. Sensitive groups should avoid it "
        "and consider an indoor alternative.",
    ),
    "Very unhealthy": (
        "The risk of health effects increases for everyone.",
        "Avoid prolonged or heavy outdoor exertion; sensitive groups should avoid outdoor "
        "physical activity. Choose an indoor alternative with cleaner air.",
    ),
    "Hazardous": (
        "Emergency air-quality conditions: everyone is more likely to be affected.",
        "Avoid outdoor physical activity and choose an indoor space with cleaner air. "
        "Check local public-health advisories.",
    ),
}


def assess(recommendation: "Recommendation") -> dict:
    """Explain the selected window; user ceilings and ranking remain in the shared scorer."""
    w, request = recommendation.window, recommendation.request
    location, forecast = recommendation.location, recommendation.forecast
    category = aqi_category(w.max_aqi)
    meaning, advice = AQI_GUIDANCE[category]
    warnings = []
    checklist = [
        "Recheck the forecast before leaving; conditions can change.",
        "Confirm the resolved location and venue access or opening hours before travelling.",
    ]
    verdict = "Best available window; review the forecast and local conditions before leaving."
    if w.max_aqi > 100:
        warnings.append(f"Worst hourly US AQI is {w.max_aqi:.0f}: {category}. {advice}")
        verdict = "Air quality remains adverse; consider an indoor alternative with cleaner air."
        if w.max_aqi > 300:
            checklist.append("Avoid outdoor physical activity; check local public-health advice.")
        elif w.max_aqi > 200:
            checklist.append(
                "Avoid prolonged or heavy outdoor activity; sensitive groups should avoid "
                "outdoor physical activity."
            )
        else:
            checklist.append(
                "Choose shorter, less strenuous activity or an indoor alternative, "
                "and follow local air-quality advice."
            )
        if request.activity == "kids":
            checklist.append(
                "Children are among the groups more sensitive to particle pollution; "
                "use the sensitive-group guidance."
            )
    elif w.max_aqi > 50:
        warnings.append(advice)

    hot = w.temperature >= 35 or (
        w.apparent_temperature is not None and w.apparent_temperature >= 35
    )
    if hot:
        apparent = (
            f"; feels like up to {w.apparent_temperature:.1f}°C"
            if w.apparent_temperature is not None
            else "; feels-like temperature is unavailable"
        )
        warnings.append(f"Heat caution: air temperature up to {w.temperature:.1f}°C{apparent}.")
        checklist.append(
            "Plan shade, drinking water and breaks; consider a cooler indoor activity."
        )
        if w.max_aqi <= 100:
            verdict = "Heat remains a concern even in the best available window."
    if w.temperature <= 0:
        warnings.append(
            f"Air temperature reaches freezing or below ({w.temperature:.1f}°C at the "
            "warmest selected hour); surface conditions need a local check."
        )
        checklist.append(
            "Check for ice and appropriate clothing before walking, running or cycling."
        )

    if w.rain_probability > 0:
        warnings.append(
            f"Peak hourly rain chance is {w.rain_probability:.0f}%; this is not the probability "
            "of rain over the entire outing."
        )
        checklist.append("Have a rain plan and check wet or slippery surfaces locally.")
        if w.rain_probability >= 70 and w.max_aqi <= 100 and not hot:
            verdict = "Rain is still likely; keep an indoor backup."
    if w.uv_index is not None and w.uv_index >= 3:
        warnings.append(f"Peak UV index is {w.uv_index:.1f}; sun protection is needed.")
        checklist.append("Use shade, protective clothing, a hat and sunscreen.")
        if w.uv_index >= 8:
            checklist.append("Avoid midday sun exposure when UV is 8 or above.")
    if request.activity == "cycle" and w.wind_speed is not None:
        checklist.append(
            f"Forecast wind reaches {w.wind_speed:.1f} km/h; check gusts, exposed sections "
            "and local riding conditions. Gust forecasts are not included here."
        )
    if w.daylight is False:
        warnings.append("The full window is not in daylight; lighting and visibility need a check.")
        checklist.append("Use daylight-only filtering if you need the entire outing before sunset.")
    missing = [
        name
        for name, value in (
            ("feels-like temperature", w.apparent_temperature),
            ("UV", w.uv_index),
            ("wind", w.wind_speed),
            ("daylight", w.daylight),
        )
        if value is None
    ]
    if missing:
        warnings.append(
            f"Unavailable context: {', '.join(missing)}. Missing data is not a favourable reading."
        )

    reasons = [
        "Chosen from complete forecast windows that match your requested duration and period.",
        f"Pollution/rain/heat preference score: {w.score:.1f}; lower is preferred. "
        "This score is not a health-risk percentage.",
        "AQI guidance uses the worst hour, so the average cannot hide a more polluted hour.",
    ]
    for field, label, units in (
        ("max_aqi", "US AQI", ""),
        ("max_rain", "rain chance", "%"),
        ("max_temperature", "feels-like temperature", "°C"),
        ("max_uv", "UV index", ""),
        ("max_wind", "wind", " km/h"),
    ):
        value = getattr(request, field)
        if value is not None:
            reasons.append(f"Every selected hour meets your {label} ceiling of {value:g}{units}.")
    if request.daylight_only:
        reasons.append("The full window meets your daylight-only requirement.")
    if forecast.is_demo:
        verdict = "Demo assessment: synthetic data; do not use for outdoor decisions."
        warnings.insert(0, "These readings are synthetic demo data, not a live forecast.")

    return {
        "verdict": verdict,
        "aqi": {
            "category": category,
            "index": w.us_aqi,
            "worst_hourly": w.max_aqi,
            "meaning": meaning,
            "advice": advice,
        },
        "location": {
            "resolved_name": location.name,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": forecast.timezone,
            "precision_note": (
                "Air quality is a regional model-grid estimate, not a station reading or "
                "street-level measurement. Nearby places can share the same forecast. "
                "A forecast does not establish a venue's quality, access or safety."
            ),
            "maps_url": "https://www.google.com/maps/search/?"
            + urlencode({"api": 1, "query": f"{location.latitude},{location.longitude}"}),
        },
        "warnings": warnings,
        "reasons": reasons,
        "checklist": checklist,
    }
