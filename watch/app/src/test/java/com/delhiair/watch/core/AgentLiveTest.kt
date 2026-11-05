package com.delhiair.watch.core

import com.delhiair.watch.data.AgentClient
import com.delhiair.watch.data.AgentReply
import com.delhiair.watch.data.AgentUnavailable
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Runs the watch's real client against a running agent: AGENT_TEST_URL=http://127.0.0.1:8080. */
class AgentLiveTest {
    private val url = System.getenv("AGENT_TEST_URL").orEmpty()
    private val agent = AgentClient(url)

    @Test
    fun theAgentPlansThroughTheWatchClient() {
        assumeTrue(url.isNotEmpty())
        val plan = (agent.ask("best 2-hour cycling window in Dwarka tomorrow morning") as AgentReply.Plan)
            .recommendation
        assertEquals("Dwarka, Delhi", plan.location.name)
        assertEquals(Activity.CYCLE, plan.request.activity)
        assertEquals(7200L, plan.window.end - plan.window.start)
    }

    @Test
    fun theAgentAnswersQuestionsAndComparesPlaces() {
        assumeTrue(url.isNotEmpty())
        val answer = agent.ask("what is the AQI in Rohini right now") as AgentReply.Answer
        assertTrue(answer.text, "Rohini" in answer.text)
        assertFalse(answer.text, "**" in answer.text)
        val compared = agent.ask("compare Hauz Khas, Delhi and Noida for a walk") as AgentReply.Compared
        assertEquals(2, compared.comparison.items.size)
    }

    @Test
    fun theAgentChoosesAPlaceAndATime() {
        assumeTrue(url.isNotEmpty())
        val walk = (agent.ask("i want to go for a walk near rohini area") as AgentReply.Plan).recommendation
        assertTrue(walk.location.name, walk.location.name.endsWith(", near Rohini"))
        assertTrue(walk.search!!.place.isNotEmpty())
        val ride = (agent.ask("go for a bike ride near Dwarka tomorrow evening") as AgentReply.Plan).recommendation
        assertEquals("DDA Dwarka Cycle Track", ride.search!!.place)
        val here = Location("Here", 28.7366, 77.1132)
        val nearby = agent.ask("a walk near me", here) as AgentReply.Plan
        assertTrue(nearby.recommendation.search!!.place.isNotEmpty())
    }

    @Test
    fun aRefusalIsNotMistakenForAnOutage() {
        assumeTrue(url.isNotEmpty())
        val message = try {
            agent.ask("walk in Noida with AQI at most 10")
            "no refusal"
        } catch (exc: AirException) {
            exc.message
        }
        assertTrue(message, "never relaxed" in message.orEmpty())
    }

    @Test(expected = AgentUnavailable::class)
    fun aDeadAgentFallsBackRatherThanCrashing() {
        AgentClient("http://127.0.0.1:9").ask("walk in Saket")
    }
}
