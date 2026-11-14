"""Download 2011 census district boundaries (not committed; ~4 MB).
Source: https://github.com/udit-001/india-maps-data  (district-level GeoJSON, census 2011 codes)
"""
from pathlib import Path
import urllib.request

URL = "https://raw.githubusercontent.com/udit-001/india-maps-data/main/geojson/india.geojson"
DEST = Path(__file__).resolve().parents[1] / "data" / "raw" / "india_districts_2011.geojson"

if __name__ == "__main__":
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        print("already present:", DEST)
    else:
        urllib.request.urlretrieve(URL, DEST)
        print("downloaded", DEST, DEST.stat().st_size // 1024, "KB")
