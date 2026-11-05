package com.delhiair.watch.core

/**
 * What the watch has learnt about its wearer. It stays on the watch: the agent only ever
 * receives the preferred activities and usual hours, with the position for that request.
 */
data class Habits(
    val activities: Map<Activity, Int> = emptyMap(),
    val hours: Map<Int, Int> = emptyMap(),
    val areas: Map<String, Int> = emptyMap(),
    val rejected: Map<Activity, Int> = emptyMap(),
) {
    fun chose(activity: Activity, hour: Int) = copy(
        activities = activities + (activity to (activities[activity] ?: 0) + 1),
        hours = hours + (hour to (hours[hour] ?: 0) + 1),
    )

    /** An hour with real movement counts towards the routine. */
    fun moved(hour: Int) = copy(hours = hours + (hour to (hours[hour] ?: 0) + 1))

    fun visited(latitude: Double, longitude: Double): Habits {
        // About 1 km cells: enough to know an area, without keeping a location trail.
        val key = "%.2f,%.2f".format(java.util.Locale.ROOT, latitude, longitude)
        return copy(areas = areas + (key to (areas[key] ?: 0) + 1))
    }

    fun declined(activity: Activity) = copy(rejected = rejected + (activity to (rejected[activity] ?: 0) + 1))

    /** Most-chosen first; each "not for me" counts against an activity twice. */
    fun favourites(): List<Activity> = OUTINGS
        .map { it to (activities[it] ?: 0) - 2 * (rejected[it] ?: 0) }
        .filter { (_, score) -> score > 0 }
        .sortedByDescending { (_, score) -> score }
        .map { (activity, _) -> activity }

    /** Hours seen at least twice, most frequent first. */
    fun usualHours(): List<Int> = hours.filterValues { it >= 2 }
        .entries.sortedByDescending { it.value }
        .take(4)
        .map { it.key }

    fun usualArea(): Pair<Double, Double>? = areas.maxByOrNull { it.value }?.key?.split(",")?.let {
        it[0].toDouble() to it[1].toDouble()
    }

    private companion object {
        val OUTINGS = listOf(Activity.WALK, Activity.RUN, Activity.CYCLE, Activity.KIDS)
    }
}

data class NotifyLog(val day: String = "", val sentToday: Int = 0, val lastSent: Long = 0, val lastKey: String = "")

private const val MAX_PER_DAY = 2
private const val MIN_GAP_SECONDS = 3 * 3600L
private const val LOOKAHEAD_SECONDS = 6 * 3600L

/**
 * An agent that interrupts too often gets turned off, so it speaks up only for something new,
 * soon and worth acting on, and never at night.
 */
fun shouldNotify(
    kind: String,
    key: String,
    windowStart: Long,
    now: Long,
    localHour: Int,
    today: String,
    log: NotifyLog,
): Boolean {
    if (localHour >= 22 || localHour < 7) return false
    val sent = if (log.day == today) log.sentToday else 0
    if (sent >= MAX_PER_DAY || now - log.lastSent < MIN_GAP_SECONDS || key == log.lastKey) return false
    // A stay-in warning is useful whenever it's new; a plan only when its time is close.
    return kind == "stay" || windowStart - now in 0..LOOKAHEAD_SECONDS
}
