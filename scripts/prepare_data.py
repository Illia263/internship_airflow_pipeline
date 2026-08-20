#!/usr/bin/env python3
"""Готує вхідні дані для завдання.

1. Качає паркет-файли Yellow Taxi 2024 з NYC TLC.
2. Ріже їх у CSV (бо bronze у реальності текстовий).
3. Робить один навмисно побитий файл (2024-06-broken).
4. Рахує еталонні суми через DECIMAL -> expected/reference.csv.

Запуск: python scripts/prepare_data.py
"""

from __future__ import annotations

import csv
import random
import sys
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"
EXPECTED = ROOT / "expected"
CACHE = ROOT / ".cache"

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
MONTHS = [f"2024-{m:02d}" for m in range(1, 13)]

# 19 колонок схеми Yellow Taxi 2024. У 2025+ додали cbd_congestion_fee -> буде 20.
COLUMNS = [
    "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count",
    "trip_distance", "RatecodeID", "store_and_fwd_flag", "PULocationID", "DOLocationID",
    "payment_type", "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
    "improvement_surcharge", "total_amount", "congestion_surcharge", "Airport_fee",
]

ROWS_PER_MONTH = 500_000   


def download(month: str) -> Path:
    CACHE.mkdir(exist_ok=True)
    dest = CACHE / f"yellow_tripdata_{month}.parquet"
    if dest.exists():
        return dest
    url = f"{BASE_URL}/yellow_tripdata_{month}.parquet"
    print(f"  loading {url}")
    tmp = dest.with_suffix(".tmp")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)
    return dest


def parquet_to_csv(parquet: Path, out: Path, limit: int) -> None:
    cols = ", ".join(f'"{c}"' for c in COLUMNS)
    duckdb.sql(f"""
        COPY (SELECT {cols} FROM read_parquet('{parquet}') LIMIT {limit})
        TO '{out}' (HEADER, DELIMITER ',')
    """)


def corrupt(src: Path, dst: Path, fraction: float = 0.30, seed: int = 42) -> int:

    rng = random.Random(seed)
    broken = 0
    with src.open(newline="") as fin, dst.open("w", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        header = next(reader)
        writer.writerow(header)
        i_pickup = header.index("tpep_pickup_datetime")
        i_dropoff = header.index("tpep_dropoff_datetime")
        i_dist = header.index("trip_distance")
        i_total = header.index("total_amount")
        i_pax = header.index("passenger_count")

        for row in reader:
            if rng.random() < fraction:
                broken += 1
                match rng.randint(0, 5):
                    case 0:
                        row[i_pickup] = row[i_pickup].replace("-", "/")
                    case 1:
                        row[i_dist] = ""
                    case 2:
                        row[i_dropoff] = row[i_pickup]
                        row[i_pickup] = row[i_dropoff]
                        row[i_dropoff] = "2020-01-01 00:00:00"
                    case 3:
                        row = row[: len(row) - 4]
                    case 4:
                        row[i_total] = "N/A"
                    case 5:
                        row[i_pax] = "1,0"
            writer.writerow(row)
    return broken


def reference_sums() -> None:
    EXPECTED.mkdir(exist_ok=True)
    files = ", ".join(f"'{SOURCE / f'yellow_tripdata_{m}.csv'}'" for m in MONTHS)
    duckdb.sql(f"""
        COPY (
            SELECT
                strftime(CAST(tpep_pickup_datetime AS TIMESTAMP), '%Y-%m') AS month,
                count(*)                                   AS rows,
                SUM(CAST(total_amount AS DECIMAL(12,2)))   AS total_amount,
                SUM(CAST(tip_amount   AS DECIMAL(12,2)))   AS tip_amount
            FROM read_csv([{files}], header=true, union_by_name=true)
            GROUP BY 1 ORDER BY 1
        ) TO '{EXPECTED / "reference.csv"}' (HEADER, DELIMITER ',')
    """)


def main() -> int:
    SOURCE.mkdir(exist_ok=True)
    print("1/4 loading ")
    for month in MONTHS:
        parquet = download(month)
        out = SOURCE / f"yellow_tripdata_{month}.csv"
        if not out.exists():
            print(f"  {month} -> csv")
            parquet_to_csv(parquet, out, ROWS_PER_MONTH)

    print("2/4 corrupting data")
    broken_src = SOURCE / "yellow_tripdata_2024-06.csv"
    broken_dst = SOURCE / "yellow_tripdata_2024-06-broken.csv"
    n = corrupt(broken_src, broken_dst)
    print(f"  corrupted {n:,} rows")

    print("3/4 calculating reference sums")
    reference_sums()

    print("4/4 done")
    print(f"\n  {SOURCE}: {len(list(SOURCE.glob('*.csv')))} files")
    print(f"  {EXPECTED / 'reference.csv'}: reference to compare with")
    return 0


if __name__ == "__main__":
    sys.exit(main())
