"""Extract Swedish postcode reference points from a downloaded GISCO 2025 ZIP.

Run with Python 3.12, input ZIP path and output JSON path. This only transforms
open geographic data; it never discovers stores or changes municipality scopes.
Uses the DBF/shapefile specification directly (point geometry only).
"""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from datetime import UTC, datetime
from pathlib import Path

SOURCE = "https://gisco-services.ec.europa.eu/distribution/v2/pcode/shp/PCODE_PT_2025_4326.shp.zip"


def extract(path):
    rows = {}
    with zipfile.ZipFile(path) as archive:
        stem = "PCODE_PT_2025_4326"
        with archive.open(stem + ".dbf") as dbf, archive.open(stem + ".shp") as shp:
            header = dbf.read(32)
            count, header_size, record_size = struct.unpack_from("<IHH", header, 4)
            descriptors = dbf.read(header_size - 32)
            fields, offset = {}, 1
            for position in range(0, len(descriptors) - 1, 32):
                descriptor = descriptors[position:position + 32]
                name = descriptor[:11].split(b"\0")[0].decode("ascii")
                length = descriptor[16]
                fields[name] = slice(offset, offset + length)
                offset += length
            assert offset == record_size
            shape_header = shp.read(100)
            assert struct.unpack_from("<I", shape_header, 32)[0] == 1
            for index in range(count):
                raw = dbf.read(record_size)
                number, size = struct.unpack(">II", shp.read(8))
                point = shp.read(size * 2)
                assert number == index + 1
                if raw[:1] == b"*" or raw[fields["CNTR_ID"]].strip() != b"SE":
                    continue
                row = {key: raw[part].decode("utf-8").strip() for key, part in fields.items()}
                postcode = re.sub(r"\s", "", row["POSTCODE"])
                assert re.fullmatch(r"[0-9]{5}", postcode)
                assert struct.unpack_from("<I", point)[0] == 1
                longitude, latitude = struct.unpack_from("<dd", point, 4)
                code = row["GISCO_2021"].removeprefix("SE_")
                assert re.fullmatch(r"[0-9]{4}", code)
                assert 54 < latitude < 70 and 10 < longitude < 25
                location = [round(latitude, 6), round(longitude, 6), code]
                # Ambiguous entries remain explicit; the API never guesses.
                if location not in rows.setdefault(postcode, []):
                    rows[postcode].append(location)
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "source_url": SOURCE,
        "source_sha256": digest,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "attribution": "© European Union - GISCO, 2024, postal code point dataset, Licence CC-BY-SA 4.0.",
        "license": "https://creativecommons.org/licenses/by-sa/4.0/",
        "basis": "GISCO postal code points 2025, Swedish subset; approximate reference points, not addresses or postal boundaries. Municipality is GISCO_2021 LAU association, not postal locality inference.",
        "columns": ["latitude", "longitude", "municipality_code"],
        "postcodes": dict(sorted(rows.items())),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = extract(args.source)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['postcodes'])} Swedish postcodes to {args.destination}")
