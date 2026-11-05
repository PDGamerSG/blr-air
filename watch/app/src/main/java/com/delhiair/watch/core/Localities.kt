package com.delhiair.watch.core

/** Mirrors delhi_air/localities.py; tests/test_delhi.py checks the two tables match. */
data class Locality(val key: String, val name: String, val latitude: Double, val longitude: Double)

val LOCALITIES: List<Locality> = listOf(
    Locality("delhi", "Delhi", 28.6139, 77.2090),
    Locality("connaught place", "Connaught Place", 28.6315, 77.2167),
    Locality("chandni chowk", "Chandni Chowk", 28.6506, 77.2303),
    Locality("karol bagh", "Karol Bagh", 28.6514, 77.1907),
    Locality("civil lines", "Civil Lines", 28.6796, 77.2244),
    Locality("bawana", "Bawana", 28.7990, 77.0330),
    Locality("rohini", "Rohini", 28.7366, 77.1132),
    Locality("punjabi bagh", "Punjabi Bagh", 28.6683, 77.1313),
    Locality("janakpuri", "Janakpuri", 28.6219, 77.0878),
    Locality("dwarka", "Dwarka", 28.5921, 77.0460),
    Locality("vasant kunj", "Vasant Kunj", 28.5200, 77.1590),
    Locality("hauz khas", "Hauz Khas", 28.5494, 77.2001),
    Locality("saket", "Saket", 28.5245, 77.2066),
    Locality("lodhi garden", "Lodhi Garden", 28.5931, 77.2197),
    Locality("india gate", "India Gate", 28.6129, 77.2295),
    Locality("lajpat nagar", "Lajpat Nagar", 28.5677, 77.2433),
    Locality("okhla", "Okhla", 28.5361, 77.2711),
    Locality("mayur vihar", "Mayur Vihar", 28.6090, 77.2950),
    Locality("anand vihar", "Anand Vihar", 28.6469, 77.3152),
    Locality("noida", "Noida", 28.5355, 77.3910),
    Locality("gurugram", "Gurugram", 28.4595, 77.0266),
    Locality("ghaziabad", "Ghaziabad", 28.6692, 77.4538),
    Locality("faridabad", "Faridabad", 28.4089, 77.3178),
)

val ALIASES: Map<String, String> = mapOf(
    "new delhi" to "delhi",
    "delhi ncr" to "delhi",
    "ncr" to "delhi",
    "dilli" to "delhi",
    "cp" to "connaught place",
    "rajiv chowk" to "connaught place",
    "old delhi" to "chandni chowk",
    "lodi garden" to "lodhi garden",
    "lodi gardens" to "lodhi garden",
    "lodhi gardens" to "lodhi garden",
    "hauz khas village" to "hauz khas",
    "hkv" to "hauz khas",
    "gurgaon" to "gurugram",
    "ggn" to "gurugram",
)

private val NCR_CITIES = setOf("noida", "gurugram", "ghaziabad", "faridabad")
val ACRONYMS = setOf("cp", "ncr", "hkv", "ggn")

private const val SECTOR = "(?:sector|sec)\\s*-?\\s*\\d+[a-z]?"
private val BY_KEY = LOCALITIES.associateBy { it.key }

private fun known(key: String): Locality? = BY_KEY[ALIASES[key] ?: key]

fun displayName(locality: Locality): String = when {
    locality.key == "delhi" -> locality.name
    locality.key in NCR_CITIES -> "${locality.name}, Delhi NCR"
    else -> "${locality.name}, Delhi"
}

fun localLocation(place: String): Location? {
    var key = place.lowercase().replace(".", "").trim()
    key = key.replace(Regex("\\s+"), " ")
    key = key.replace(Regex("[,\\s]+india$"), "")
    // Sector numbers are finer than the model grid, so "Sector 62, Noida" resolves to Noida.
    val sector = Regex("^$SECTOR[,\\s]+|[,\\s]+$SECTOR$")
    val city = key.replace(Regex("[,\\s]+(?:new delhi|delhi ncr|delhi|ncr|uttar pradesh|haryana)$"), "")
    // Look the whole name up first: "new delhi" must not lose its " delhi" suffix.
    val found = known(key.replace(sector, "")) ?: known(city) ?: known(city.replace(sector, "")) ?: return null
    return Location(displayName(found), found.latitude, found.longitude, "Asia/Kolkata")
}
