package com.delhiair.watch.core

/** Mirrors delhi_air/domain.py. Times are epoch seconds so hours stay elapsed hours. */
enum class Activity(val key: String, val label: String, val verb: String) {
    RUN("run", "Run", "run"),
    CYCLE("cycle", "Cycle", "cycle"),
    WALK("walk", "Walk", "walk"),
    COMMUTE("commute", "Commute", "commute"),
    KIDS("kids", "Kids", "take children outside");

    companion object {
        fun of(key: String?) = entries.firstOrNull { it.key == key } ?: WALK
    }
}

enum class Day(val key: String, val label: String) {
    NEXT48("next48", "Next 48 hours"),
    TODAY("today", "Today"),
    TOMORROW("tomorrow", "Tomorrow");

    companion object {
        fun of(key: String?) = entries.firstOrNull { it.key == key } ?: NEXT48
    }
}

enum class Period(val key: String, val label: String, val startHour: Int, val endHour: Int) {
    ANY("any", "Any time", 5, 21),
    MORNING("morning", "Morning", 5, 12),
    AFTERNOON("afternoon", "Afternoon", 12, 17),
    EVENING("evening", "Evening", 17, 21);

    companion object {
        fun of(key: String?) = entries.firstOrNull { it.key == key } ?: ANY
    }
}

data class PlanRequest(
    val place: String = "Delhi",
    val activity: Activity = Activity.WALK,
    val hours: Int = 1,
    val day: Day = Day.NEXT48,
    val period: Period = Period.ANY,
    val places: List<String> = emptyList(),
    val maxAqi: Double? = null,
    val maxRain: Double? = null,
    val maxTemperature: Double? = null,
    val maxUv: Double? = null,
    val maxWind: Double? = null,
    val daylightOnly: Boolean = false,
)

data class Location(
    val name: String,
    val latitude: Double,
    val longitude: Double,
    val timezone: String? = null,
)

data class Hour(
    val time: Long,
    val usAqi: Double,
    val pm25: Double,
    val rain: Double,
    val temperature: Double,
    val apparent: Double? = null,
    val uv: Double? = null,
    val wind: Double? = null,
)

data class CurrentAir(val time: Long, val usAqi: Double, val pm25: Double)

data class Sunlight(val rise: Long, val set: Long)

data class Forecast(
    val hours: List<Hour>,
    val current: CurrentAir?,
    val timezone: String,
    val fetchedAt: Long,
    val daylight: List<Sunlight> = emptyList(),
)

data class Window(
    val start: Long,
    val end: Long,
    val usAqi: Double,
    val pm25: Double,
    val rain: Double,
    val temperature: Double,
    val maxAqi: Double,
    val score: Double,
    val apparent: Double? = null,
    val uv: Double? = null,
    val wind: Double? = null,
    val daylight: Boolean? = null,
)

/** An actionable error that can be shown on the watch. */
open class AirException(message: String) : Exception(message)

class NoWindowException : AirException(
    "No complete outdoor window matches this request in the next 48 hours. " +
        "Try 1 hour, another part of the day, or explicitly adjust your limits. " +
        "Missing data cannot satisfy a limit; limits are never relaxed automatically.",
)

class ProviderException(message: String) : AirException(message)

class LocationException(message: String) : AirException(message)
