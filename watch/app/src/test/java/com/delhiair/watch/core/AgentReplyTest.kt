package com.delhiair.watch.core

import com.delhiair.watch.data.AgentReply
import com.delhiair.watch.data.parseAgentReply
import com.delhiair.watch.data.plainText
import com.delhiair.watch.data.refusal
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The fixtures are real replies recorded from POST /api/ask. */
class AgentReplyTest {
    private fun fixture(name: String) = JSONObject(ParityTest.resource(name))

    private fun JSONArray.strings() = List(length()) { getString(it) }

    @Test
    fun aPlanBecomesARecommendationTheWatchCanShow() {
        val raw = fixture("agent_plan.json")
        val reply = parseAgentReply(raw) as AgentReply.Plan
        val plan = reply.recommendation
        assertEquals("Dwarka, Delhi", plan.location.name)
        assertEquals(Activity.CYCLE, plan.request.activity)
        assertEquals(2, plan.request.hours)
        assertEquals(Day.TOMORROW, plan.request.day)
        assertEquals(Period.MORNING, plan.request.period)
        assertEquals(raw.getJSONArray("backups").length(), plan.backups.size)
        assertNotNull(plan.forecast.current)
        assertTrue(plan.window.end > plan.window.start)
    }

    @Test
    fun theWatchAssessesTheAgentsWindowExactlyAsTheAgentDoes() {
        val raw = fixture("agent_plan.json")
        val plan = (parseAgentReply(raw) as AgentReply.Plan).recommendation
        val expected = raw.getJSONObject("window").getJSONObject("assessment")
        val actual = assess(plan.window, plan.request)
        assertEquals(expected.getString("verdict"), actual.verdict)
        assertEquals(expected.getJSONArray("warnings").strings(), actual.warnings)
        assertEquals(expected.getJSONArray("checklist").strings(), actual.checklist)
    }

    @Test
    fun aComparisonKeepsTheAgentsSharedCellFinding() {
        val raw = fixture("agent_compare.json")
        val comparison = (parseAgentReply(raw) as AgentReply.Compared).comparison
        assertEquals(raw.getString("winner"), comparison.winner)
        assertEquals(listOf(listOf("Hauz Khas, Delhi", "Noida, Delhi NCR")), comparison.sharedAirModel)
        assertEquals(3, comparison.items.size)
    }

    @Test
    fun aFailedPlaceInAComparisonStaysVisible() {
        val raw = fixture("agent_compare.json")
        raw.getJSONArray("places").put(
            JSONObject().put("place", "Atlantis").put("status", "error").put("error", "Not found"),
        )
        val comparison = (parseAgentReply(raw) as AgentReply.Compared).comparison
        assertEquals("Not found", comparison.items.last().error)
    }

    @Test
    fun aPlaceSearchBringsThePlaceAndItsAlternatives() {
        val raw = fixture("agent_spot.json")
        val plan = (parseAgentReply(raw) as AgentReply.Plan).recommendation
        val found = plan.search!!
        assertEquals(raw.getJSONObject("search").getString("place"), found.place)
        assertTrue(plan.location.name, plan.location.name.endsWith(", near Rohini"))
        assertEquals(2, found.others.size)
        assertTrue(found.why, found.area in found.why)
    }

    @Test
    fun aRefusalKeepsItsReason() {
        assertEquals("No window", refusal(JSONObject("""{"status":"error","error":"No window"}""")))
        val allFailed = """{"status":"error","places":[{"place":"X","error":"Not found"}]}"""
        assertEquals("Not found", refusal(JSONObject(allFailed)))
        assertEquals("The agent couldn't do that.", refusal(JSONObject("{}")))
    }

    @Test
    fun answersLoseTheirMarkdown() {
        val explained = parseAgentReply(fixture("agent_answer.json")) as AgentReply.Answer
        assertFalse(explained.text, "**" in explained.text)
        assertTrue(explained.text, "300 is Very unhealthy" in explained.text)
        val conditions = parseAgentReply(fixture("agent_conditions.json")) as AgentReply.Answer
        assertTrue(conditions.text, "Rohini, Delhi" in conditions.text)
        assertEquals("Open maps", plainText("[Open maps](https://example.com)"))
        assertEquals("• one\n• two", plainText("- one\n- two"))
    }
}
