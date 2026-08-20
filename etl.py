"""Те, що зараз працює в проді. Автор — стажер, якого вже немає.

НЕ ПЕРЕПИСУЙ З НУЛЯ. Читай README.md.
"""

import csv
import os
from datetime import datetime
from decimal import Decimal
import argparse
import psycopg2
import requests
import json
import sys
import structlog
import uuid
from structlog.contextvars import bind_contextvars, clear_contextvars
from tenacity import retry, wait_random_exponential, retry_if_exception_type, stop_after_attempt
import tempfile


DB = psycopg2.connect("dbname=taxi user=postgres password=postgres host=localhost")

log_file = open("etl.log", "a", encoding='utf-8') 
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
        

    ],
   logger_factory=structlog.WriteLoggerFactory(file=log_file)
)
logger = structlog.get_logger()

@retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(3), retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError)), reraise=True)
def download(month, dest="/tmp/data"):
    logger.info('download_started', month=month, destination = dest)
    url = f"http://localhost:8000/yellow_tripdata_{month}.csv"
    r = requests.get(url)
    r.raise_for_status()
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, f"{month}.csv")
    open(path, "wb").write(r.content)
    return path


def load(path, target_month):
    logger.info("load_started", path=path)
    error_count = 0
    total_rows = 0
    def rows_parsing(rows):
        nonlocal total_rows
        for r in rows:
            
            total_rows += 1
            if not r["tpep_pickup_datetime"].startswith(target_month):
                yield("bad", {'raw-data' : r, 'reason' : 'This date was not requested'})
                continue
            try:
                parsed = {
                    "vendor": int(r["VendorID"]),
                    "pickup": datetime.strptime(r["tpep_pickup_datetime"], "%Y-%m-%d %H:%M:%S"),
                    "dist": float(r["trip_distance"]),
                    "total": Decimal(r["total_amount"]),
                }
                yield("good", parsed)
                

            except Exception as e:
                logger.warning("row_parsing_failed", reason=str(e), vendor_id = r.get("VendorID"))
                yield("bad", {'raw-data' : r, 'reason' : str(e)})


    
    with open(path, 'r') as raw_f, open("dead-letter.ndjson", 'a', encoding='utf-8') as dead_letter, tempfile.TemporaryFile("w+", newline='',  encoding='utf8') as temp_csv:
        rows = csv.DictReader(raw_f)
        stream = rows_parsing(rows)
        writer = csv.writer(temp_csv)
        for status, item in stream:
            if status == "good":
                 writer.writerow([
                      item['vendor'],
                      item['pickup'],
                      item['dist'],
                      item['total']
                 ])
                

            elif status == "bad":
                error_count += 1
                
                json.dump(item, dead_letter, ensure_ascii=False)
                dead_letter .write("\n")
        if total_rows > 0:
            temp_csv.seek(0)

            with DB.cursor() as cursor:

                cursor.execute(""" CREATE TEMP TABLE temp_trips (
                        vendor INTEGER,
                        pickup TIMESTAMP,
                        dist DOUBLE PRECISION, 
                        total NUMERIC ) ON COMMIT DROP;
                        """)
                cursor.copy_expert( 
                    """
                        COPY temp_trips (vendor, pickup, dist, total)
                        FROM STDIN WITH (FORMAT csv); 
                        """, temp_csv) 
                
                cursor.execute(
                """ INSERT INTO trips(vendor, pickup, dist, total)
                    SELECT vendor, pickup, dist, total
                    FROM temp_trips
                    ON CONFLICT (vendor, pickup, dist) DO NOTHING;
                
                
                """
                
                
            )



    
    if total_rows ==0:
        return 0
        

    error_rate = error_count / total_rows
    if error_rate > 0.05:
        logger.error("More than 5'%' of broken rows", total_loaded = total_rows - error_count, error_count=error_count)
        DB.rollback()
        sys.exit(1)
        
            
    DB.commit()
    return total_rows - error_count


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", type=str)
    parser.add_argument("--backfill",type=str)
    data = parser.parse_args()
    clear_contextvars()
    run_id = str(uuid.uuid4())
    bind_contextvars(run_id=run_id)
    logger.info("pipeline_started", target_month = data.month)
    try:
        if data.month:

            path = download(data.month)
            loaded_rows_count = load(path, data.month)
            logger.info("Pipeline_completed_successfully", final_rows=loaded_rows_count)
        elif data.backfill:
            start_month, end_month = data.backfill.split(":") #2024-01:202412
            year = start_month.split("-")[0]
            start_mnth = int(start_month.split("-")[1])
            end_mnth = int(end_month.split("-")[1])
            for m in range (start_mnth, end_mnth+1):
                current_month = f"{year}-{m:02d}"
                path = download(current_month)
                loaded_rows_count = load(path, current_month)
                logger.info("Pipeline_completed_successfully", final_rows=loaded_rows_count)
            
        else:
            logger.error("No --month or --backfill detected")
            sys.exit(2)
    except (requests.exceptions.RequestException, psycopg2.Error) as e:
        logger.exception('infrastructure error', error=str(e) )
        sys.exit(2)



if __name__ == "__main__":
    run()
