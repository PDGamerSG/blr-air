import difflib
import re

from delhi_air.domain import Location

# Approximate neighbourhood centroids, not sensor locations.
LOCALITIES = {
    "delhi": ("Delhi", 28.6139, 77.2090),
    "connaught place": ("Connaught Place", 28.6315, 77.2167),
    "chandni chowk": ("Chandni Chowk", 28.6506, 77.2303),
    "karol bagh": ("Karol Bagh", 28.6514, 77.1907),
    "civil lines": ("Civil Lines", 28.6796, 77.2244),
    "rohini": ("Rohini", 28.7366, 77.1132),
    "bawana": ("Bawana", 28.7990, 77.0330),
    "punjabi bagh": ("Punjabi Bagh", 28.6683, 77.1313),
    "janakpuri": ("Janakpuri", 28.6219, 77.0878),
    "dwarka": ("Dwarka", 28.5921, 77.0460),
    "vasant kunj": ("Vasant Kunj", 28.5200, 77.1590),
    "hauz khas": ("Hauz Khas", 28.5494, 77.2001),
    "saket": ("Saket", 28.5245, 77.2066),
    "lodhi garden": ("Lodhi Garden", 28.5931, 77.2197),
    "india gate": ("India Gate", 28.6129, 77.2295),
    "lajpat nagar": ("Lajpat Nagar", 28.5677, 77.2433),
    "okhla": ("Okhla", 28.5361, 77.2711),
    "mayur vihar": ("Mayur Vihar", 28.6090, 77.2950),
    "anand vihar": ("Anand Vihar", 28.6469, 77.3152),
    "noida": ("Noida", 28.5355, 77.3910),
    "gurugram": ("Gurugram", 28.4595, 77.0266),
    "ghaziabad": ("Ghaziabad", 28.6692, 77.4538),
    "faridabad": ("Faridabad", 28.4089, 77.3178),
}
ALIASES = {
    "new delhi": "delhi",
    "delhi ncr": "delhi",
    "ncr": "delhi",
    "dilli": "delhi",
    "cp": "connaught place",
    "rajiv chowk": "connaught place",
    "old delhi": "chandni chowk",
    "lodi garden": "lodhi garden",
    "lodi gardens": "lodhi garden",
    "lodhi gardens": "lodhi garden",
    "hauz khas village": "hauz khas",
    "hkv": "hauz khas",
    "gurgaon": "gurugram",
    "ggn": "gurugram",
}
# Neighbouring cities in the National Capital Region are not part of Delhi itself.
NCR_CITIES = {"noida", "gurugram", "ghaziabad", "faridabad"}
# Upper-case forms for abbreviations when a place is recovered from free text.
ACRONYMS = {"cp", "ncr", "hkv", "ggn"}

# Speech recognisers often turn Delhi names into English words.
MISHEARD = {
    "socket": "saket",
    "sake it": "saket",
    "house cause": "hauz khas",
    "hose khas": "hauz khas",
    "house khas": "hauz khas",
    "how's cause": "hauz khas",
    "bhavana": "bawana",
    "bhawana": "bawana",
    "havana": "bawana",
}

_SECTOR = r"(?:sector|sec)\s*-?\s*\d+[a-z]?"


def _known(key: str) -> str | None:
    key = ALIASES.get(key, key)
    return key if key in LOCALITIES else None


def local_location(place: str) -> Location | None:
    key = re.sub(r"[.]+", "", place.casefold()).strip()
    key = re.sub(r"\s+", " ", key)
    key = re.sub(r"[,\s]+india$", "", key)
    # Sector numbers are finer than the model grid, so "Sector 62, Noida" resolves to Noida.
    plain = re.sub(rf"^{_SECTOR}[,\s]+|[,\s]+{_SECTOR}$", "", key)
    city = re.sub(r"[,\s]+(?:new delhi|delhi ncr|delhi|ncr|uttar pradesh|haryana)$", "", key)
    # Look the whole name up first: "new delhi" must not lose its " delhi" suffix.
    found = (
        _known(plain)
        or _known(city)
        or _known(re.sub(rf"^{_SECTOR}[,\s]+|[,\s]+{_SECTOR}$", "", city))
    )
    if found is None:
        return None
    name, latitude, longitude = LOCALITIES[found]
    if found != "delhi":
        name = f"{name}, {'Delhi NCR' if found in NCR_CITIES else 'Delhi'}"
    return Location(name, latitude, longitude, "Asia/Kolkata")


def closest_location(place: str) -> Location | None:
    """The Delhi NCR name a misheard or misspelt word most likely means.

    Only for area searches, which cover Delhi NCR alone: a planner request must stay free to
    name a real town elsewhere, such as Okha, whose spelling is close to Okhla.
    """
    key = re.sub(r"\s+", " ", place.casefold()).strip(" .,?!")
    if key in MISHEARD:
        return local_location(MISHEARD[key])
    match = difflib.get_close_matches(key, [*LOCALITIES, *ALIASES], n=1, cutoff=0.72)
    return local_location(match[0]) if match else None
