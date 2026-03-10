# Version: 0.6.13-examples.3
"""Bundled input processing example that reads a CSV file and writes reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

INPUT_CSV_PATH = Path("data") / "sample_readings.csv"
OUTPUT_FIELDS = ["timestamp", "device", "reading", "band", "reading_delta_from_average"]


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    """Return all CSV rows as dictionaries."""
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _band_for_value(reading: int) -> str:
    """Map a numeric reading into a simple band."""
    if reading >= 80:
        return "high"
    if reading >= 60:
        return "medium"
    return "low"


def _write_processed_csv(path: Path, processed_rows: list[dict[str, str]]) -> None:
    """Write transformed rows to a deterministic CSV file."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(processed_rows)


def main() -> None:
    """Read bundled CSV input and write transformed deterministic outputs."""
    rows = _load_rows(INPUT_CSV_PATH)
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    readings = [int(row["reading"]) for row in rows]
    average_reading = sum(readings) / len(readings)
    rounded_average = int(round(average_reading))
    high_count = 0
    medium_count = 0
    low_count = 0
    processed_rows: list[dict[str, str]] = []

    print(f"Loaded {len(rows)} input rows from {INPUT_CSV_PATH.as_posix()}")
    for row in rows:
        reading = int(row["reading"])
        band = _band_for_value(reading)
        if band == "high":
            high_count += 1
        elif band == "medium":
            medium_count += 1
        else:
            low_count += 1
        processed_rows.append(
            {
                "timestamp": row["timestamp"],
                "device": row["device"],
                "reading": str(reading),
                "band": band,
                "reading_delta_from_average": str(reading - rounded_average),
            }
        )
        print(f"Processed {row['device']} reading at {row['timestamp']}: {reading} -> {band}")

    _write_processed_csv(outputs_dir / "processed.csv", processed_rows)
    stats = {
        "example_id": "03_process_input_files",
        "input_row_count": len(rows),
        "reading_sum": sum(readings),
        "reading_average": rounded_average,
        "min_reading": min(readings),
        "max_reading": max(readings),
        "band_counts": {"high": high_count, "medium": medium_count, "low": low_count},
    }
    (outputs_dir / "stats.json").write_text(
        json.dumps(stats, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_lines = [
        "# Process input files summary",
        "",
        f"Input file: `{INPUT_CSV_PATH.as_posix()}`",
        f"Rows processed: {len(rows)}",
        f"Reading sum: {sum(readings)}",
        f"Average reading: {rounded_average}",
        f"Bands: high={high_count}, medium={medium_count}, low={low_count}",
    ]
    (outputs_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print("Wrote outputs/processed.csv, outputs/stats.json, and outputs/summary.md")


if __name__ == "__main__":
    main()
