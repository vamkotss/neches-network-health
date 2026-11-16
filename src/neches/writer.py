"""Writes rows to the landing zone: one gzip-compressed JSONL file per arrival hour."""

import gzip
import json
from pathlib import Path

import numpy as np


def _to_python(name: str, values: np.ndarray) -> list:
    """Turn one numpy column into a plain Python list that json can write."""
    if name == "event_time":
        # Times become text like 2026-11-01T00:05:00Z (the Z means UTC).
        return [text + "Z" for text in values.astype("datetime64[s]").astype(str).tolist()]
    return values.tolist()  # numbers and text become plain Python numbers and text


def write_landing(records: dict[str, np.ndarray], out_dir) -> list[Path]:
    """Write one file per arrival hour. Returns the list of files written."""
    out_dir = Path(out_dir)
    # arrival_time is not written inside the rows; it lives in the folder path instead.
    fields = [name for name in records if name != "arrival_time"]
    hours = records["arrival_time"].astype("datetime64[h]")  # arrival time rounded to the hour
    # Sort rows by arrival hour, then event time, then device. A fixed order means
    # the same input always produces identical files.
    order = np.lexsort(
        (records["device_id"], records["event_time"].astype("int64"), hours.astype("int64"))
    )
    sorted_hours = hours[order]
    # Find where each new hour begins in the sorted rows.
    starts = np.flatnonzero(np.r_[True, sorted_hours[1:] != sorted_hours[:-1]])
    ends = np.r_[starts[1:], len(order)]  # each group ends where the next one starts
    written = []  # the files we create
    for start, end in zip(starts, ends):
        rows = order[start:end]  # row numbers belonging to this arrival hour
        text = str(sorted_hours[start])  # looks like 2026-11-01T05
        folder = out_dir / "landing" / "telemetry" / f"dt={text[:10]}" / f"hour={text[11:13]}"
        folder.mkdir(parents=True, exist_ok=True)  # create the folders if needed
        path = folder / "batch_0001.jsonl.gz"
        columns = {name: _to_python(name, records[name][rows]) for name in fields}
        # mtime=0 and an empty filename keep the gzip header identical on every run.
        with (
            open(path, "wb") as raw,
            gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped,
        ):
            for i in range(len(rows)):
                line = {name: columns[name][i] for name in fields}  # one reading
                zipped.write((json.dumps(line) + "\n").encode())  # one JSON line
        written.append(path)
    return written
