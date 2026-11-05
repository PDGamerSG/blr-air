package com.delhiair.watch.core

import com.delhiair.watch.data.parseForecast
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.BeforeClass
import org.junit.Test

/** Every expected value here was produced by the Python agent (watch/tools/gen_parity.py). */
class ParityTest {
    companion object {
        private lateinit var parity: JSONObject

        fun resource(name: String): String =
            ParityTest::class.java.classLoader!!.getResource(name)!!.readText()

        @JvmStatic
        @BeforeClass
        fun load() {
            parity = JSONObject(resource("parity.json"))
        }
    }

    private fun JSONObject.nullable(key: String): Double? =
        if (isNull(key)) null else getDouble(key)

    private fun JSONArray.objects() = List(length()) { getJSONObject(it) }

    private fun JSONArray.strings() = List(length()) { getString(it) }

    private fun hour(row: JSONObject) = Hour(
        row.getLong("time"),
        row.getDouble("us_aqi"),
        row.getDouble("pm2_5"),
        row.getDouble("rain_probability"),
        row.getDouble("temperature"),
        row.nullable("apparent_temperature"),
        row.nullable("uv_index"),
        row.nullable("wind_speed"),
    )

    private fun request(json: JSONObject) = PlanRequest(
        activity = Activity.of(json.getString("activity")),
        hours = json.getInt("hours"),
        day = Day.of(json.getString("day")),
        period = Period.of(json.getString("period")),
        maxAqi = json.nullable("max_aqi"),
        maxRain = json.nullable("max_rain"),
        maxTemperature = json.nullable("max_temperature"),
        maxUv = json.nullable("max_uv"),
        maxWind = json.nullable("max_wind"),
        daylightOnly = json.getBoolean("daylight_only"),
    )

    private fun near(label: String, expected: Double?, actual: Double?) {
        if (expected == null) {
            assertNull(label, actual)
        } else {
            assertEquals(label, expected, actual!!, 1e-9)
        }
    }

    private fun assertWindow(label: String, expected: JSONObject, actual: Window) {
        assertEquals("$label start", expected.getLong("start"), actual.start)
        assertEquals("$label end", expected.getLong("end"), actual.end)
        near("$label aqi", expected.getDouble("us_aqi"), actual.usAqi)
        near("$label pm", expected.getDouble("pm2_5"), actual.pm25)
        near("$label rain", expected.getDouble("rain_probability"), actual.rain)
        near("$label temperature", expected.getDouble("temperature"), actual.temperature)
        near("$label worst", expected.getDouble("max_aqi"), actual.maxAqi)
        near("$label score", expected.getDouble("score"), actual.score)
        near("$label apparent", expected.nullable("apparent_temperature"), actual.apparent)
        near("$label uv", expected.nullable("uv_index"), actual.uv)
        near("$label wind", expected.nullable("wind_speed"), actual.wind)
        val daylight = if (expected.isNull("daylight")) null else expected.getBoolean("daylight")
        assertEquals("$label daylight", daylight, actual.daylight)
    }

    @Test
    fun scoringAndAssessmentMatchPython() {
        val cases = parity.getJSONArray("scoring").objects()
        var withWindows = 0
        var refused = 0
        cases.forEachIndexed { index, case ->
            val rows = case.getJSONArray("rows").objects().map(::hour)
            val planRequest = request(case.getJSONObject("request"))
            val daylight = case.getJSONArray("daylight").let { list ->
                List(list.length()) { i ->
                    list.getJSONArray(i).let { Sunlight(it.getLong(0), it.getLong(1)) }
                }
            }
            val zone = case.getString("timezone")
            val now = case.getLong("now")
            if (case.isNull("windows")) {
                refused++
                try {
                    selectWindows(rows, planRequest, zone, now, 3, daylight)
                    fail("case $index should have no window")
                } catch (_: NoWindowException) {
                    return@forEachIndexed
                }
            }
            val expected = case.getJSONArray("windows").objects()
            val actual = selectWindows(rows, planRequest, zone, now, 3, daylight)
            assertEquals("case $index window count", expected.size, actual.size)
            withWindows++
            val assessments = case.getJSONArray("assessments").objects()
            expected.indices.forEach { i ->
                assertWindow("case $index window $i", expected[i], actual[i])
                val result = assess(actual[i], planRequest)
                val wanted = assessments[i]
                assertEquals("case $index verdict", wanted.getString("verdict"), result.verdict)
                assertEquals("case $index category", wanted.getString("category"), result.category)
                assertEquals("case $index advice", wanted.getString("advice"), result.advice)
                assertEquals("case $index warnings", wanted.getJSONArray("warnings").strings(), result.warnings)
                assertEquals("case $index checklist", wanted.getJSONArray("checklist").strings(), result.checklist)
            }
        }
        // Guards against a fixture that quietly stops exercising one of the two paths.
        assertTrue("windows: $withWindows", withWindows > 150)
        assertTrue("refusals: $refused", refused > 50)
    }

    @Test
    fun sentencesParseLikePython() {
        for (case in parity.getJSONArray("parser").objects()) {
            val text = case.getString("text")
            if (case.has("error")) {
                val message = try {
                    parseLocal(text)
                    "parsed"
                } catch (exc: AirException) {
                    exc.message
                }
                assertEquals(text, case.getString("error"), message)
                continue
            }
            val wanted = case.getJSONObject("request")
            val actual = parseLocal(text)
            assertEquals("$text place", wanted.getString("place"), actual.place)
            assertEquals("$text places", wanted.getJSONArray("places").strings(), actual.places)
            assertEquals("$text activity", wanted.getString("activity"), actual.activity.key)
            assertEquals("$text hours", wanted.getInt("hours"), actual.hours)
            assertEquals("$text day", wanted.getString("day"), actual.day.key)
            assertEquals("$text period", wanted.getString("period"), actual.period.key)
            near("$text aqi", wanted.nullable("max_aqi"), actual.maxAqi)
            near("$text rain", wanted.nullable("max_rain"), actual.maxRain)
            near("$text feels", wanted.nullable("max_temperature"), actual.maxTemperature)
            near("$text uv", wanted.nullable("max_uv"), actual.maxUv)
            near("$text wind", wanted.nullable("max_wind"), actual.maxWind)
            assertEquals("$text daylight", wanted.getBoolean("daylight_only"), actual.daylightOnly)
        }
    }

    @Test
    fun placesResolveLikePython() {
        for (case in parity.getJSONArray("locations").objects()) {
            val text = case.getString("text")
            val actual = localLocation(text)
            if (!case.has("name")) {
                assertNull(text, actual)
                continue
            }
            assertEquals(text, case.getString("name"), actual?.name)
            near("$text latitude", case.getDouble("latitude"), actual!!.latitude)
            near("$text longitude", case.getDouble("longitude"), actual.longitude)
            assertEquals(text, case.getString("timezone"), actual.timezone)
        }
    }

    @Test
    fun categoriesMatchPython() {
        for (case in parity.getJSONArray("categories").objects()) {
            assertEquals(case.getString("category"), aqiCategory(case.getDouble("aqi")))
        }
    }

    @Test
    fun recordedDelhiForecastParsesLikePython() {
        val wanted = parity.getJSONObject("forecast")
        val actual = parseForecast(
            JSONObject(resource("air_delhi.json")),
            JSONObject(resource("weather_delhi.json")),
            1_793_800_000,
        )
        assertEquals(wanted.getString("timezone"), actual.timezone)
        val hours = wanted.getJSONArray("hours").objects()
        assertTrue("hours: ${hours.size}", hours.size >= 90)
        assertEquals(hours.map(::hour), actual.hours)
        val current = wanted.getJSONObject("current")
        assertEquals(current.getLong("time"), actual.current!!.time)
        near("current aqi", current.getDouble("us_aqi"), actual.current!!.usAqi)
        val daylight = wanted.getJSONArray("daylight")
        assertEquals(daylight.length(), actual.daylight.size)
        assertEquals(daylight.getJSONArray(0).getLong(0), actual.daylight[0].rise)
    }
}
