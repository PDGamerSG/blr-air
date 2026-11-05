package com.delhiair.watch.core

import java.math.BigDecimal
import java.math.RoundingMode

/** Port of delhi_air/assessment.py. AssessmentParityTest compares its text with Python's. */
val AQI_GUIDANCE: Map<String, Pair<String, String>> = mapOf(
    "Good" to (
        "Air quality is satisfactory; air pollution poses little or no risk for most people." to
            "Continue to check local conditions and your own response to outdoor activity."
        ),
    "Moderate" to (
        "Air quality is acceptable, but unusually sensitive people may still be affected." to
            "If you are unusually sensitive to air pollution, consider reducing prolonged or " +
            "heavy outdoor exertion."
        ),
    "Unhealthy for sensitive groups" to (
        "Sensitive groups may experience health effects; the general public is less likely " +
            "to be affected." to
            "Sensitive groups should reduce prolonged or heavy outdoor exertion; consider an " +
            "indoor alternative. Follow your clinician's advice for an existing condition."
        ),
    "Unhealthy" to (
        "Everyone may begin to experience health effects; sensitive groups may have " +
            "more serious effects." to
            "Reduce prolonged or heavy outdoor exertion. Sensitive groups should avoid it " +
            "and consider an indoor alternative."
        ),
    "Very unhealthy" to (
        "The risk of health effects increases for everyone." to
            "Avoid prolonged or heavy outdoor exertion; sensitive groups should avoid outdoor " +
            "physical activity. Choose an indoor alternative with cleaner air."
        ),
    "Hazardous" to (
        "Emergency air-quality conditions: everyone is more likely to be affected." to
            "Avoid outdoor physical activity and choose an indoor space with cleaner air. " +
            "Check local public-health advisories."
        ),
)

data class Assessment(
    val verdict: String,
    val category: String,
    val meaning: String,
    val advice: String,
    val warnings: List<String>,
    val checklist: List<String>,
)

/** Python's format() rounds the exact binary value half-to-even; String.format does not. */
fun fixed(value: Double, places: Int): String =
    BigDecimal(value).setScale(places, RoundingMode.HALF_EVEN).toPlainString()

fun assess(window: Window, request: PlanRequest): Assessment {
    val category = aqiCategory(window.maxAqi)
    val (meaning, advice) = AQI_GUIDANCE.getValue(category)
    val warnings = mutableListOf<String>()
    val checklist = mutableListOf(
        "Recheck the forecast before leaving; conditions can change.",
        "Confirm the resolved location and venue access or opening hours before travelling.",
    )
    var verdict = "Best available window; review the forecast and local conditions before leaving."
    if (window.maxAqi > 100) {
        warnings += "Worst hourly US AQI is ${fixed(window.maxAqi, 0)}: $category. $advice"
        verdict = "Air quality remains adverse; consider an indoor alternative with cleaner air."
        checklist += when {
            window.maxAqi > 300 ->
                "Avoid outdoor physical activity; check local public-health advice."
            window.maxAqi > 200 ->
                "Avoid prolonged or heavy outdoor activity; sensitive groups should avoid " +
                    "outdoor physical activity."
            else ->
                "Choose shorter, less strenuous activity or an indoor alternative, " +
                    "and follow local air-quality advice."
        }
        if (request.activity == Activity.KIDS) {
            checklist += "Children are among the groups more sensitive to particle pollution; " +
                "use the sensitive-group guidance."
        }
    } else if (window.maxAqi > 50) {
        warnings += advice
    }

    val apparent = window.apparent
    val hot = window.temperature >= 35 || (apparent != null && apparent >= 35)
    if (hot) {
        val feels = if (apparent != null) {
            "; feels like up to ${fixed(apparent, 1)}°C"
        } else {
            "; feels-like temperature is unavailable"
        }
        warnings += "Heat caution: air temperature up to ${fixed(window.temperature, 1)}°C$feels."
        checklist += "Plan shade, drinking water and breaks; consider a cooler indoor activity."
        if (window.maxAqi <= 100) verdict = "Heat remains a concern even in the best available window."
    }
    if (window.temperature <= 0) {
        warnings += "Air temperature reaches freezing or below (${fixed(window.temperature, 1)}°C " +
            "at the warmest selected hour); surface conditions need a local check."
        checklist += "Check for ice and appropriate clothing before walking, running or cycling."
    }
    if (window.rain > 0) {
        warnings += "Peak hourly rain chance is ${fixed(window.rain, 0)}%; this is not the " +
            "probability of rain over the entire outing."
        checklist += "Have a rain plan and check wet or slippery surfaces locally."
        if (window.rain >= 70 && window.maxAqi <= 100 && !hot) {
            verdict = "Rain is still likely; keep an indoor backup."
        }
    }
    val uv = window.uv
    if (uv != null && uv >= 3) {
        warnings += "Peak UV index is ${fixed(uv, 1)}; sun protection is needed."
        checklist += "Use shade, protective clothing, a hat and sunscreen."
        if (uv >= 8) checklist += "Avoid midday sun exposure when UV is 8 or above."
    }
    val wind = window.wind
    if (request.activity == Activity.CYCLE && wind != null) {
        checklist += "Forecast wind reaches ${fixed(wind, 1)} km/h; check gusts, exposed sections " +
            "and local riding conditions. Gust forecasts are not included here."
    }
    if (window.daylight == false) {
        warnings += "The full window is not in daylight; lighting and visibility need a check."
        checklist += "Use daylight-only filtering if you need the entire outing before sunset."
    }
    val missing = listOf(
        "feels-like temperature" to window.apparent,
        "UV" to window.uv,
        "wind" to window.wind,
        "daylight" to window.daylight,
    ).filter { it.second == null }.map { it.first }
    if (missing.isNotEmpty()) {
        warnings += "Unavailable context: ${missing.joinToString(", ")}. " +
            "Missing data is not a favourable reading."
    }
    return Assessment(verdict, category, meaning, advice, warnings, checklist)
}
