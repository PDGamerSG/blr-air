package com.delhiair.watch.core

import com.delhiair.watch.data.distanceKm
import com.delhiair.watch.data.parseGeocoding
import com.delhiair.watch.data.parseStation
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.OffsetDateTime

class StationAndCompareTest {
    private val shanghai = JSONObject(ParityTest.resource("waqi_shanghai.json"))
    private val shanghaiTime = OffsetDateTime
        .parse(shanghai.getJSONObject("data").getJSONObject("time").getString("iso"))
        .toEpochSecond()

    private fun delhiStation(aqi: Any = 312, iso: String = "2026-11-04T18:00:00+05:30") = JSONObject(
        """
        {"status":"ok","data":{"aqi":${JSONObject.quote(aqi.toString()).let { if (aqi is Int) aqi else it }},
        "idx":2553,"attributions":[{"name":"CPCB - India Central Pollution Control Board"}],
        "city":{"geo":[28.647622,77.315809],"name":"Anand Vihar, Delhi, India"},
        "iaqi":{"pm25":{"v":312}},"time":{"iso":"$iso","v":1793798000}}}
        """.trimIndent(),
    )

    private val now = OffsetDateTime.parse("2026-11-04T18:30:00+05:30").toEpochSecond()

    @Test
    fun aRealWaqiResponseParsesWhenTheStationIsNearby() {
        val geo = shanghai.getJSONObject("data").getJSONObject("city").getJSONArray("geo")
        val station = parseStation(shanghai, geo.getDouble(0), geo.getDouble(1), shanghaiTime + 600)
        assertNotNull(station)
        assertEquals(shanghai.getJSONObject("data").getInt("aqi"), station!!.aqi)
        assertEquals(0.0, station.distanceKm, 0.01)
    }

    @Test
    fun aFarAwayStationIsNeverPassedOffAsLocalAir() {
        // WAQI's demo token really does answer a Delhi query with Shanghai.
        assertNull(parseStation(shanghai, 28.6469, 77.3152, shanghaiTime + 600))
    }

    @Test
    fun anandViharReadsItsOwnStation() {
        val station = parseStation(delhiStation(), 28.6469, 77.3152, now)
        assertEquals(312, station!!.aqi)
        assertEquals("Anand Vihar, Delhi, India", station.name)
        assertEquals("CPCB - India Central Pollution Control Board", station.attribution)
        assertFalse(station.isStale(now))
    }

    @Test
    fun aRecordedDelhiStationResponseParses() {
        val payload = JSONObject(ParityTest.resource("waqi_anand_vihar.json"))
        val stamp = payload.getJSONObject("data").getJSONObject("time").getString("iso")
        val time = OffsetDateTime.parse(stamp).toEpochSecond()
        val station = parseStation(payload, 28.6469, 77.3152, time + 600)!!
        assertTrue(station.name, station.name.startsWith("Anand Vihar"))
        assertEquals(payload.getJSONObject("data").getInt("aqi"), station.aqi)
        assertEquals("pm10", station.dominant)
        assertTrue(station.isLocal)
    }

    @Test
    fun aDistantStationIsContextNotTheLocalReading() {
        // Ghaziabad has no monitor in this feed; Anand Vihar is its nearest, 13.7 km away.
        val station = parseStation(delhiStation(), 28.6692, 77.4538, now)!!
        assertFalse(station.isLocal)
        assertEquals(13.7, station.distanceKm, 0.5)
    }

    @Test
    fun aStationWithoutAReadingIsIgnored() {
        assertNull(parseStation(delhiStation(aqi = "-"), 28.6469, 77.3152, now))
    }

    @Test
    fun oldReadingsAreFlaggedThenDropped() {
        val hoursOld = parseStation(delhiStation(iso = "2026-11-04T12:00:00+05:30"), 28.6469, 77.3152, now)
        assertTrue(hoursOld!!.isStale(now))
        assertNull(parseStation(delhiStation(iso = "2026-11-02T12:00:00+05:30"), 28.6469, 77.3152, now))
    }

    @Test
    fun aFailedLookupHasNoStation() {
        assertNull(parseStation(JSONObject("""{"status":"error","data":"Invalid key"}"""), 28.6, 77.2, now))
    }

    @Test
    fun distanceIsRealistic() {
        // Connaught Place to Noida is about 20 km.
        assertEquals(20.0, distanceKm(28.6315, 77.2167, 28.5355, 77.3910), 2.0)
    }

    private fun forecast(aqi: Double): Forecast {
        val start = OffsetDateTime.parse("2026-11-05T08:00:00+05:30").toEpochSecond()
        val hours = (0 until 8).map { Hour(start + it * 3600L, aqi, 100.0, 0.0, 24.0) }
        return Forecast(hours, null, "Asia/Kolkata", now)
    }

    private fun item(name: String, aqi: Double) = ComparisonItem(
        name,
        recommend(PlanRequest(), Location(name, 28.6, 77.2), forecast(aqi), now),
    )

    @Test
    fun comparisonRanksByScoreAndKeepsFailuresLast() {
        val result = Comparison(
            listOf(
                ComparisonItem("Nowhere", error = "Unavailable"),
                item("Rohini", 250.0),
                item("Saket", 200.0),
            ),
        )
        assertEquals("Saket", result.winner)
        assertEquals(listOf("Saket", "Rohini", "Nowhere"), result.items.map { it.place })
        assertTrue(result.tiedPlaces.isEmpty())
        assertTrue(result.sharedAirModel.isEmpty())
    }

    @Test
    fun monitorsThatContradictTheForecastRankingAreFlagged() {
        val hotspot = item("Anand Vihar", 200.0).copy(measuredAqi = 313.0)
        val quieter = item("Hauz Khas", 225.0).copy(measuredAqi = 183.0)
        val result = Comparison(listOf(quieter, hotspot))
        assertEquals("Anand Vihar", result.winner)
        assertEquals("Hauz Khas", result.cleanerNow)
    }

    @Test
    fun noContradictionIsClaimedWithoutTwoMeasurementsOrAClearGap() {
        val leader = item("Saket", 200.0).copy(measuredAqi = 210.0)
        assertNull(Comparison(listOf(leader, item("Noida", 225.0))).cleanerNow)
        val close = item("Rohini", 225.0).copy(measuredAqi = 190.0)
        assertNull(Comparison(listOf(leader, close)).cleanerNow)
    }

    @Test
    fun placesInOneModelCellAreDisclosed() {
        val result = Comparison(listOf(item("Hauz Khas", 227.0), item("Noida", 227.0)))
        assertEquals(listOf(listOf("Hauz Khas", "Noida")), result.sharedAirModel)
        assertEquals(listOf("Hauz Khas", "Noida"), result.tiedPlaces)
    }

    @Test
    fun geocodingHonoursCountryQualifiers() {
        val payload = JSONObject(
            """{"results":[
            {"name":"Delhi","admin1":"Ontario","country":"Canada","country_code":"CA","latitude":42.85,"longitude":-80.5,"timezone":"America/Toronto"},
            {"name":"Paris","admin1":"Ile-de-France","country":"France","country_code":"FR","latitude":48.85,"longitude":2.35,"timezone":"Europe/Paris"}]}""",
        )
        assertEquals("Paris, Ile-de-France, France", parseGeocoding(payload, "Paris, France").name)
    }

    @Test
    fun coordinatesNeverReachTheGeocoderAndReadAsAPlace() {
        val geocoder = com.delhiair.watch.data.Http { error("must not call the geocoder: $it") }
        val near = com.delhiair.watch.data.locate("28.6500, 77.3100", geocoder)
        assertEquals("Near Anand Vihar", near.name)
        assertEquals(28.65, near.latitude, 1e-9)
        assertEquals("My location", com.delhiair.watch.data.locate("37.4234, -122.0840", geocoder).name)
        assertNull(com.delhiair.watch.data.coordinateLocation("Hauz Khas"))
        assertNull(com.delhiair.watch.data.coordinateLocation("95.0, 77.0"))
    }

    @Test
    fun theVerdictIsStricterForChildrenAndHardExercise() {
        fun window(aqi: Double, rain: Double = 0.0, heat: Double = 25.0) =
            Window(0, 3600, aqi, 50.0, rain, heat, aqi, 0.0)
        val walk = PlanRequest()
        val run = PlanRequest(activity = Activity.RUN)
        assertEquals(Verdict.GO, verdictFor(window(80.0), walk))
        assertEquals(Verdict.CARE, verdictFor(window(130.0), walk))
        assertEquals(Verdict.SHORT, verdictFor(window(180.0), walk))
        assertEquals(Verdict.STAY, verdictFor(window(180.0), run))
        assertEquals(Verdict.STAY, verdictFor(window(260.0), walk))
        assertEquals(Verdict.RAIN, verdictFor(window(80.0, rain = 80.0), walk))
        assertEquals(Verdict.HEAT, verdictFor(window(80.0, heat = 38.0), walk))
    }

    @Test
    fun spokenAnswerNamesRiskAndSource() {
        val text = spokenSummary(item("Saket, Delhi", 220.0).recommendation!!)
        assertTrue(text, text.startsWith("Saket,"))
        assertTrue(text, "Consider staying indoors" in text)
        assertTrue(text, "not medical advice" in text)
        // At about 15 characters a second, this stays under a quarter of a minute.
        assertTrue("${text.length} characters", text.length < 200)
    }
}
