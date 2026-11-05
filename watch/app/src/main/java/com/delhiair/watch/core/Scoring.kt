package com.delhiair.watch.core

import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId

/** Port of delhi_air/scoring.py. ScoringParityTest checks it against fixtures from Python. */
private const val HOUR = 3600L
private const val HORIZON = 48 * HOUR

fun aqiCategory(aqi: Double): String = when {
    aqi <= 50 -> "Good"
    aqi <= 100 -> "Moderate"
    aqi <= 150 -> "Unhealthy for sensitive groups"
    aqi <= 200 -> "Unhealthy"
    aqi <= 300 -> "Very unhealthy"
    else -> "Hazardous"
}

/** A preference heuristic, not a health or exposure model. Lower is better. */
fun hourlyCost(row: Hour): Double =
    row.usAqi + 0.5 * row.pm25 + 1.5 * row.rain + 5 * maxOf(0.0, row.temperature - 30)

private class Candidate(val score: Double, val start: Long, val block: List<Hour>)

private fun exceeds(block: List<Hour>, limit: Double?, value: (Hour) -> Double?): Boolean {
    if (limit == null) return false
    return block.any { row -> value(row).let { it == null || it > limit } }
}

private fun completePeak(block: List<Hour>, value: (Hour) -> Double?): Double? {
    val values = block.map(value)
    return if (values.all { it != null }) values.maxOf { it!! } else null
}

fun selectWindows(
    rows: List<Hour>,
    request: PlanRequest,
    timezone: String,
    now: Long,
    limit: Int = 1,
    daylight: List<Sunlight> = emptyList(),
): List<Window> {
    require(limit in 1..3) { "Choose between one and three windows." }
    val zone = ZoneId.of(timezone)
    val today = Instant.ofEpochSecond(now).atZone(zone).toLocalDate()
    val targetDay = when (request.day) {
        Day.TODAY -> today
        Day.TOMORROW -> today.plusDays(1)
        Day.NEXT48 -> null
    }
    val startHour = request.period.startHour
    val endHour = request.period.endHour
    // Later rows replace earlier ones with the same timestamp, as a Python dict does.
    val ordered = rows.associateBy { it.time }.values.sortedBy { it.time }
    val candidates = mutableListOf<Candidate>()
    for (i in 0..(ordered.size - request.hours)) {
        val block = ordered.subList(i, i + request.hours)
        val first = block.first().time
        val end = block.last().time + HOUR
        if (first < now || end > now + HORIZON) continue
        if (block.zipWithNext().any { (a, b) -> b.time - a.time != HOUR }) continue
        val local = block.map { Instant.ofEpochSecond(it.time).atZone(zone) }
        if (local.any { it.hour !in startHour until endHour }) continue
        val localEnd = Instant.ofEpochSecond(end).atZone(zone)
        if (localEnd.toLocalDate() != local.first().toLocalDate()) continue
        if (localEnd.toLocalTime() > LocalTime.of(endHour, 0)) continue
        if (targetDay != null && local.any { it.toLocalDate() != targetDay }) continue
        if (request.daylightOnly && daylight.none { it.rise <= first && end <= it.set }) continue
        if (exceeds(block, request.maxAqi) { it.usAqi }) continue
        if (exceeds(block, request.maxRain) { it.rain }) continue
        if (exceeds(block, request.maxTemperature) { it.apparent }) continue
        if (exceeds(block, request.maxUv) { it.uv }) continue
        if (exceeds(block, request.maxWind) { it.wind }) continue
        candidates += Candidate(block.sumOf(::hourlyCost) / block.size, first, block)
    }
    if (candidates.isEmpty()) throw NoWindowException()

    val ranked = candidates.sortedWith(compareBy<Candidate> { it.score }.thenBy { it.start })
    val selected = mutableListOf<Candidate>()
    for (candidate in ranked) {
        val start = candidate.start
        val end = candidate.block.last().time + HOUR
        val overlaps = selected.any {
            start < it.block.last().time + HOUR && end > it.start
        }
        if (overlaps) continue
        selected += candidate
        if (selected.size >= limit) break
    }
    return selected.map { candidate ->
        val block = candidate.block
        val start = candidate.start
        val end = block.last().time + HOUR
        Window(
            start = start,
            end = end,
            usAqi = block.sumOf { it.usAqi } / block.size,
            pm25 = block.sumOf { it.pm25 } / block.size,
            rain = block.maxOf { it.rain },
            temperature = block.maxOf { it.temperature },
            maxAqi = block.maxOf { it.usAqi },
            score = candidate.score,
            apparent = completePeak(block) { it.apparent },
            uv = completePeak(block) { it.uv },
            wind = completePeak(block) { it.wind },
            daylight = if (daylight.isEmpty()) {
                null
            } else {
                daylight.any { it.rise <= start && end <= it.set }
            },
        )
    }
}
