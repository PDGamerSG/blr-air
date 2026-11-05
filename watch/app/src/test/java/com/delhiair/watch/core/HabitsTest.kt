package com.delhiair.watch.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HabitsTest {
    @Test
    fun theMostChosenActivityComesFirst() {
        var habits = Habits()
        repeat(3) { habits = habits.chose(Activity.RUN, 7) }
        habits = habits.chose(Activity.WALK, 18)
        assertEquals(listOf(Activity.RUN, Activity.WALK), habits.favourites())
    }

    @Test
    fun notForMeOutweighsAChoice() {
        val habits = Habits().chose(Activity.RUN, 7).chose(Activity.WALK, 7).declined(Activity.RUN)
        assertEquals(listOf(Activity.WALK), habits.favourites())
    }

    @Test
    fun anHourBecomesUsualOnlyWhenRepeated() {
        val once = Habits().moved(7)
        assertTrue(once.usualHours().isEmpty())
        assertEquals(listOf(7), once.moved(7).chose(Activity.WALK, 18).usualHours())
    }

    @Test
    fun aRoutineIsLearntFromMovementAsWellAsChoices() {
        val habits = Habits().moved(18).chose(Activity.WALK, 18)
        assertEquals(listOf(18), habits.usualHours())
    }

    @Test
    fun areasAreCoarseAndTheCommonestWins() {
        val habits = Habits().visited(28.7366, 77.1132).visited(28.7371, 77.1129).visited(28.52, 77.20)
        assertEquals(28.74 to 77.11, habits.usualArea())
        assertEquals(2, habits.areas.size)
    }

    private val now = 1_800_000_000L

    private fun notify(
        kind: String = "short",
        key: String = "a",
        start: Long = now + 3600,
        hour: Int = 12,
        log: NotifyLog = NotifyLog(),
    ) = shouldNotify(kind, key, start, now, hour, "2026-11-06", log)

    @Test
    fun aGoodWindowSoonIsWorthAMessage() {
        assertTrue(notify())
    }

    @Test
    fun itStaysQuietAtNight() {
        assertFalse(notify(hour = 23))
        assertFalse(notify(hour = 6))
    }

    @Test
    fun itDoesntRepeatItself() {
        assertFalse(notify(log = NotifyLog(lastKey = "a")))
    }

    @Test
    fun itDoesntNag() {
        assertFalse(notify(log = NotifyLog("2026-11-06", 2, now - 20000, "b")))
        assertFalse(notify(log = NotifyLog("2026-11-06", 1, now - 600, "b")))
        assertTrue(notify(log = NotifyLog("2026-11-05", 2, now - 20000, "b")))
    }

    @Test
    fun aWindowFarAwayCanWait() {
        assertFalse(notify(start = now + 8 * 3600))
        assertFalse(notify(start = now - 60))
    }

    @Test
    fun aStayInWarningDoesntNeedANearbyWindow() {
        assertTrue(notify(kind = "stay", start = now + 30 * 3600))
    }
}
