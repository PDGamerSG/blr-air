package com.delhiair.watch.core

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs

/** The planning layer of delhi_air/service.py, sized for a watch. */
const val AIR_MODEL_NOTE =
    "The air model covers about 45 km per cell. It cannot see local hotspots such as busy " +
        "junctions or industrial areas, so a nearby place ranking higher is not evidence of " +
        "cleaner air."
const val MEASURED_GAP = 50.0
const val LIMITATION = "Model forecasts, not CPCB station readings or medical advice."
const val SOURCE = "Open-Meteo Air Quality (CAMS) and Weather Forecast"

data class Recommendation(
    val request: PlanRequest,
    val location: Location,
    val forecast: Forecast,
    val window: Window,
    val backups: List<Window>,
    /** What the agent found when it chose the place itself. */
    val search: PlaceSearch? = null,
)

data class PlaceSearch(
    val place: String,
    val why: String,
    val checked: Int,
    val searched: Int,
    val area: String,
    val others: List<OtherPlace>,
)

data class OtherPlace(val place: String, val distanceKm: Double, val time: String, val aqi: Int, val measured: Int?)

fun recommend(request: PlanRequest, location: Location, forecast: Forecast, now: Long): Recommendation {
    val windows = selectWindows(forecast.hours, request, forecast.timezone, now, 3, forecast.daylight)
    return Recommendation(request, location, forecast, windows.first(), windows.drop(1))
}

data class ComparisonItem(
    val place: String,
    val recommendation: Recommendation? = null,
    val error: String? = null,
    /** A nearby station's reading, when there is one. */
    val measuredAqi: Double? = null,
)

/** Valid places first, best score first; ties keep the order the user chose. */
class Comparison(items: List<ComparisonItem>, private val knownShared: List<List<String>>? = null) {
    val items: List<ComparisonItem> =
        items.filter { it.recommendation != null }.sortedBy { it.recommendation!!.window.score } +
            items.filter { it.recommendation == null }

    val winner: String? get() = items.firstOrNull { it.recommendation != null }?.place

    val tiedPlaces: List<String>
        get() {
            val valid = items.filter { it.recommendation != null }
            if (valid.isEmpty()) return emptyList()
            val best = valid.first().recommendation!!.window.score
            val tied = valid.filter { abs(it.recommendation!!.window.score - best) <= 1e-6 }
            return if (tied.size > 1) tied.map { it.place } else emptyList()
        }

    /** A place monitors show as clearly cleaner right now than the forecast's winner. */
    val cleanerNow: String?
        get() {
            val valid = items.filter { it.recommendation != null }
            val leader = valid.firstOrNull()?.measuredAqi ?: return null
            val cleanest = valid.drop(1).filter { it.measuredAqi != null }.minByOrNull { it.measuredAqi!! }
            return cleanest?.takeIf { leader - it.measuredAqi!! >= MEASURED_GAP }?.place
        }

    /** Groups of places with identical hourly air forecasts: one model cell covers them. */
    val sharedAirModel: List<List<String>>
        get() = knownShared ?: items.mapNotNull { it.recommendation }
            .groupBy { rec -> rec.forecast.hours.map { Triple(it.time, it.usAqi, it.pm25) } }
            .values
            .filter { it.size > 1 }
            .map { group -> group.map { it.location.name } }
}

private val CLOCK = DateTimeFormatter.ofPattern("HH:mm", Locale.ENGLISH)
private val DAY = DateTimeFormatter.ofPattern("EEE d MMM", Locale.ENGLISH)
private val SPOKEN_DAY = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ENGLISH)

fun clock(epoch: Long, timezone: String): String =
    CLOCK.format(Instant.ofEpochSecond(epoch).atZone(ZoneId.of(timezone)))

fun dayLabel(epoch: Long, timezone: String): String =
    DAY.format(Instant.ofEpochSecond(epoch).atZone(ZoneId.of(timezone)))

fun windowLabel(window: Window, timezone: String): String =
    "${dayLabel(window.start, timezone)} · ${clock(window.start, timezone)}–${clock(window.end, timezone)}"

/** A short English answer for text-to-speech; it keeps the risk and the source. */
fun spokenSummary(rec: Recommendation): String {
    val w = rec.window
    val tz = rec.forecast.timezone
    val risk = if (w.maxAqi > 100 || w.temperature >= 35 || w.rain >= 70) {
        " Consider staying indoors."
    } else {
        ""
    }
    val day = SPOKEN_DAY.format(Instant.ofEpochSecond(w.start).atZone(ZoneId.of(tz)))
    return "${rec.location.name.substringBefore(",")}, $day, ${clock(w.start, tz)} to " +
        "${clock(w.end, tz)}. Air quality ${fixed(w.usAqi, 0)}, ${aqiCategory(w.maxAqi)}.$risk " +
        "Model forecast, not medical advice."
}
