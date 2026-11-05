"""Rebuild delhi_air/spots.json from OpenStreetMap, whose data is licensed under the ODbL.

Run from the repository root:
    .venv/Scripts/python scripts/build_spots.py
"""

import json
import math
import re
from pathlib import Path

import httpx

OUT = Path(__file__).parent.parent / "delhi_air/spots.json"
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
QUERY = """[out:json][timeout:90];
(
  nwr["leisure"~"^(park|garden|nature_reserve|track|stadium)$"]["name"](28.38,76.93,28.88,77.55);
  nwr["boundary"="protected_area"]["name"](28.38,76.93,28.88,77.55);
);
out tags bb;"""
MIN_AREA_M2 = 6000
SKIP = re.compile(
    r"\b(?:parking|private|society|residential|apartment|cgh[s]?|regulated area|esz|"
    r"green land|green belt|bundh|bund)\b",
    re.I,
)


def area_m2(element) -> float:
    box = element.get("bounds")
    if not box:
        return 0.0
    height = (box["maxlat"] - box["minlat"]) * 111_000
    width = (box["maxlon"] - box["minlon"]) * 111_000 * math.cos(math.radians(box["minlat"]))
    # A bounding box overstates an irregular park, so count roughly two-thirds of it.
    return height * width * 0.65


def spot(element):
    tags = element.get("tags", {})
    name = tags.get("name:en") or tags.get("name", "")
    box = element.get("bounds")
    if not box or not name.isascii() or len(name) < 4 or SKIP.search(name):
        return None
    area = area_m2(element)
    if area < MIN_AREA_M2:
        return None
    if tags.get("access") in ("private", "no"):
        return None
    return {
        "name": name.strip(),
        "latitude": round((box["minlat"] + box["maxlat"]) / 2, 5),
        "longitude": round((box["minlon"] + box["maxlon"]) / 2, 5),
        "kind": tags.get("leisure") or "protected_area",
        "area_m2": round(area, -2),
        "cycling": tags.get("bicycle") not in ("no", "dismount"),
    }


def main():
    headers = {"User-Agent": "delhi-air-agent/0.1 (hackathon project)"}
    for endpoint in (*ENDPOINTS, *ENDPOINTS):
        try:
            response = httpx.post(endpoint, data={"data": QUERY}, headers=headers, timeout=120)
            response.raise_for_status()
            elements = response.json()["elements"]
            break
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            print(endpoint, type(exc).__name__, str(exc)[:80])
    else:
        raise SystemExit("All Overpass endpoints failed.")
    spots = {}
    for element in elements:
        item = spot(element)
        if item:
            key = item["name"].casefold()
            if key not in spots or item["area_m2"] > spots[key]["area_m2"]:
                spots[key] = item
    ranked = sorted(spots.values(), key=lambda item: -item["area_m2"])
    OUT.write_text(json.dumps(ranked, indent=0, ensure_ascii=True), encoding="utf-8")
    print(f"{len(elements)} elements, {len(ranked)} spots")


if __name__ == "__main__":
    main()
