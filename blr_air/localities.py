import re

from blr_air.domain import Location

# Approximate neighbourhood centroids, not sensor locations.
LOCALITIES = {
    "bengaluru": ("Bengaluru", 12.9716, 77.5946),
    "hsr layout": ("HSR Layout", 12.9116, 77.6389),
    "koramangala": ("Koramangala", 12.9352, 77.6245),
    "indiranagar": ("Indiranagar", 12.9784, 77.6408),
    "whitefield": ("Whitefield", 12.9698, 77.7500),
    "electronic city": ("Electronic City", 12.8452, 77.6602),
    "jayanagar": ("Jayanagar", 12.9250, 77.5938),
    "jp nagar": ("JP Nagar", 12.9063, 77.5857),
    "btm layout": ("BTM Layout", 12.9166, 77.6101),
    "bellandur": ("Bellandur", 12.9304, 77.6784),
    "marathahalli": ("Marathahalli", 12.9591, 77.6974),
    "sarjapur": ("Sarjapur", 12.8600, 77.7860),
    "yelahanka": ("Yelahanka", 13.1005, 77.5963),
    "hebbal": ("Hebbal", 13.0354, 77.5988),
    "malleshwaram": ("Malleshwaram", 13.0031, 77.5643),
    "rajajinagar": ("Rajajinagar", 12.9915, 77.5530),
    "banashankari": ("Banashankari", 12.9255, 77.5468),
    "basavanagudi": ("Basavanagudi", 12.9422, 77.5738),
    "cubbon park": ("Cubbon Park", 12.9763, 77.5929),
    "lalbagh": ("Lalbagh", 12.9507, 77.5848),
}
ALIASES = {
    "bangalore": "bengaluru",
    "hsr": "hsr layout",
    "j p nagar": "jp nagar",
    "btm": "btm layout",
    "e city": "electronic city",
    "malleswaram": "malleshwaram",
}


def local_location(place: str) -> Location | None:
    key = re.sub(r"[.]+", "", place.casefold()).strip()
    key = re.sub(r"[,\s]+(?:bengaluru|bangalore)(?:[,\s]+india)?$", "", key)
    key = ALIASES.get(key, key)
    item = LOCALITIES.get(key)
    if item:
        name, latitude, longitude = item
        return Location(
            name if key == "bengaluru" else f"{name}, Bengaluru",
            latitude,
            longitude,
            "Asia/Kolkata",
        )
    return None
