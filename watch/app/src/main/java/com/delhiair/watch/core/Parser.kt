package com.delhiair.watch.core

/** Port of parse_local in delhi_air/parsing.py, used for spoken requests on the watch. */
private val I = RegexOption.IGNORE_CASE

private val UNSUPPORTED = Regex(
    "\\b(next week|next month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\\b" +
        "|\\b(?:after|before|at|between|from)\\s+\\d|\\b\\d{4}-\\d{2}-\\d{2}\\b" +
        "|\\b\\d{1,2}(?::\\d{2}|\\s*[ap]\\.?m\\.?)\\b|\\bday after tomorrow\\b" +
        "|\\b\\d+\\s*[- ]?\\s*(?:minutes?|mins?)\\b",
    I,
)
private val NEXT_48 = Regex("(?:in\\s+)?(?:the\\s+)?next\\s+48\\s+hours?", I)
private const val COMPARISON =
    "\\s*(?:at most|up to|under|below|max(?:imum)?|less than|no more than|<=|≤)\\s*"
private const val NUMBER = "(-?\\d+(?:\\.\\d+)?)"

fun validateText(raw: String): String {
    val text = raw.replace(Regex("@(?:blr|delhi)-air\\b", I), "").trim()
    if (text.isEmpty() || text.length > 2000) {
        throw AirException("Send a short request, for example: 'best 1-hour run in Hauz Khas'.")
    }
    if (UNSUPPORTED.containsMatchIn(text)) {
        throw AirException(
            "I support the next 48 hours, today or tomorrow, optionally morning, " +
                "afternoon or evening. Exact clock times and later dates aren't supported.",
        )
    }
    return text
}

private class Limits {
    var aqi: Double? = null
    var rain: Double? = null
    var temperature: Double? = null
    var uv: Double? = null
    var wind: Double? = null
    var daylight = false
}

private fun extractLimits(input: String, limits: Limits): String {
    var text = input
    val fields = listOf(
        Triple("aqi", "(?:us\\s+)?aqi", ""),
        Triple("rain", "rain(?:\\s+(?:chance|probability))?", "\\s*%?"),
        Triple(
            "temperature",
            "(?:feels[ -]like(?:\\s+temperature)?|temperature|heat)",
            "(?:\\s*°?\\s*(celsius|fahrenheit|kelvin|[cfk])\\b)?",
        ),
        Triple("uv", "uv(?:\\s+index)?", ""),
        Triple("wind", "wind(?:\\s+speed)?", "(?:\\s*(km/h|kmh|kph|mph|m/s|knots)\\b)?"),
    )
    for ((field, label, unit) in fields) {
        val patterns = listOf(
            Regex("\\b$label$COMPARISON$NUMBER$unit", I),
            Regex("\\bmax(?:imum)?\\s+$label\\s*[:=]?\\s*$NUMBER$unit", I),
        )
        val values = mutableListOf<Double>()
        for (pattern in patterns) {
            for (match in pattern.findAll(text)) {
                var value = match.groupValues[1].toDouble()
                if (field == "temperature" || field == "wind") {
                    val unitName = match.groupValues.getOrElse(2) { "" }.lowercase()
                    if (unitName in setOf("kelvin", "k", "knots")) {
                        throw AirException("Use °C or °F for temperature and km/h, mph or m/s for wind.")
                    }
                    if (field == "temperature" && unitName in setOf("f", "fahrenheit")) {
                        value = (value - 32) * 5 / 9
                    } else if (field == "wind" && unitName == "mph") {
                        value *= 1.609344
                    } else if (field == "wind" && unitName == "m/s") {
                        value *= 3.6
                    }
                }
                values += value
            }
            text = pattern.replace(text, "")
        }
        val strictest = values.minOrNull()
        when (field) {
            "aqi" -> if (strictest != null) limits.aqi = strictest
            "rain" -> if (strictest != null) limits.rain = strictest
            "temperature" -> if (strictest != null) limits.temperature = strictest
            "uv" -> if (strictest != null) limits.uv = strictest
            "wind" -> if (strictest != null) limits.wind = strictest
        }
    }
    val daylight = Regex("\\b(?:daylight only|only in daylight|daytime only)\\b", I)
    if (daylight.containsMatchIn(text)) {
        limits.daylight = true
        text = daylight.replace(text, "")
    }
    if (Regex("\\b(?:aqi|rain|feels[ -]like|temperature|heat|uv|wind)\\b[^.!?;]{0,45}\\d", I).containsMatchIn(text)) {
        throw AirException(
            "I couldn't read that weather limit. Use 'AQI at most 100', 'rain at most 30%', " +
                "or the exact CLI/API limit fields.",
        )
    }
    return text
}

private fun comparisonPlaces(text: String): List<String> {
    if (!Regex("\\b(?:compare|between)\\b|\\b(?:vs|versus)\\b", I).containsMatchIn(text)) {
        return emptyList()
    }
    var body = Regex("^.*?\\b(?:compare|between)\\s+", I).replaceFirst(text, "")
    body = Regex("^.*?\\bin\\s+", I).replaceFirst(body, "")
    body = Regex("\\s+\\b(?:for|today|tomorrow|this|morning|afternoon|evening|with)\\b", I)
        .split(body, 2)[0]
        .trim(' ', '.', ',', '?', '!')
    val places = Regex("\\s+(?:and|vs\\.?|versus|or)\\s+|\\s*;\\s*", I).split(body)
        .map { it.trim(' ', '.', ',', '?', '!') }
    val expanded = places.flatMap { place ->
        val parts = place.split(",").map { it.trim() }
        val split = parts.size > 1 && localLocation(place) == null && parts.all { localLocation(it) != null }
        if (split) parts else listOf(place)
    }
    if (expanded.size !in 2..3) {
        throw AirException("Compare two or three places, for example: 'compare Hauz Khas and Noida'.")
    }
    return expanded
}

private fun titleCase(name: String) = name.split(" ").joinToString(" ") { word ->
    word.replaceFirstChar { it.titlecase() }
}

fun parseLocal(input: String): PlanRequest {
    var text = validateText(input)
    text = Regex(
        "\\b(?:show\\s+)?(?:customer\\s+)?(?:reviews?|ratings?|opening hours|accessibility)" +
            "\\s+(?:of|for)\\s+",
        I,
    ).replace(text, "in ")
    text = Regex("\\s+(?:and|with)\\s+(?:show\\s+)?(?:customer\\s+)?(?:reviews?|ratings?)\\b", I)
        .replace(text, "")
    val limits = Limits()
    text = extractLimits(text, limits)
    val lower = text.lowercase()

    val durationText = NEXT_48.replace(lower, "")
    val duration = Regex("\\b(\\d+|one|two|three|four)\\s*[- ]?\\s*(?:hours?|hrs?)\\b").find(durationText)
    val hours = duration?.let {
        val token = it.groupValues[1]
        mapOf("one" to 1, "two" to 2, "three" to 3, "four" to 4)[token] ?: token.toIntOrNull()
    } ?: 1
    if (hours !in 1..2) throw AirException("Choose a 1-hour or 2-hour outdoor window.")

    val activity = listOf(
        "\\b(kids?|children|child|playground)\\b" to Activity.KIDS,
        "\\b(cycle|cycling|bike|biking)\\b" to Activity.CYCLE,
        "\\b(run|runs|running|jog|jogging)\\b" to Activity.RUN,
        "\\b(commute|commuting)\\b" to Activity.COMMUTE,
    ).firstOrNull { Regex(it.first).containsMatchIn(lower) }?.second ?: Activity.WALK
    val day = listOf(Day.TOMORROW, Day.TODAY)
        .firstOrNull { Regex("\\b${it.key}\\b").containsMatchIn(lower) } ?: Day.NEXT48
    val period = listOf(Period.MORNING, Period.AFTERNOON, Period.EVENING)
        .firstOrNull { Regex("\\b${it.key}\\b").containsMatchIn(lower) } ?: Period.ANY

    val places = comparisonPlaces(text)
    // Remove temporal clauses before extracting place; "in the next 48 hours" is not a city.
    val cleaned = NEXT_48.replace(text, "")
    var place = Regex("\\b(?:in|near|at)\\s+(.+)", I).find(cleaned)?.let { match ->
        Regex("\\b(?:today|tomorrow|this|for|during|with|morning|afternoon|evening)\\b", I)
            .split(match.groupValues[1], 2)[0]
            .trim(' ', '.', ',', '?', '!')
    }.orEmpty()
    if (place.isEmpty()) {
        val names = (LOCALITIES.map { it.key } + ALIASES.keys).sortedByDescending { it.length }
        val name = names.firstOrNull {
            Regex("(?<!\\w)" + Regex.escape(it) + "(?!\\w)").containsMatchIn(lower)
        }
        if (name != null) place = if (name in ACRONYMS) name.uppercase() else titleCase(name)
    }
    if (place.isEmpty()) {
        // Retain unrecognised words as a possible place instead of silently defaulting.
        var residue = Regex("\\b(?:\\d+|one|two)\\s*[- ]?\\s*(?:hours?|hrs?)\\b", I).replace(cleaned, " ")
        residue = Regex(
            "\\b(?:best|when|what|is|the|a|an|can|i|my|to|for|go|take|should|please|" +
                "time|times|window|windows|air|quality|cleanest|aqi|pm2\\.5|" +
                "run|runs|running|jog|jogging|walk|walking|cycle|cycling|bike|biking|" +
                "commute|commuting|kids?|children|child|outside|outdoors?|weather|pollution|smog|haze|" +
                "today|tomorrow|this|morning|afternoon|evening)\\b",
            I,
        ).replace(residue, " ")
        place = residue.replace(Regex("\\s+"), " ").trim(' ', '.', ',', '?', '!')
    }
    val resolved = places.firstOrNull() ?: place.ifEmpty { "Delhi" }
    val inRange = (limits.aqi ?: 0.0) in 0.0..500.0 && (limits.rain ?: 0.0) in 0.0..100.0 &&
        (limits.temperature ?: 0.0) in -80.0..70.0 && (limits.uv ?: 0.0) in 0.0..30.0 &&
        (limits.wind ?: 0.0) in 0.0..200.0
    if (resolved.length !in 2..160 || !inRange) {
        throw AirException("Please give a city or Delhi locality and a 1- or 2-hour activity.")
    }
    return PlanRequest(
        place = resolved,
        activity = activity,
        hours = hours,
        day = day,
        period = period,
        places = places,
        maxAqi = limits.aqi,
        maxRain = limits.rain,
        maxTemperature = limits.temperature,
        maxUv = limits.uv,
        maxWind = limits.wind,
        daylightOnly = limits.daylight,
    )
}
