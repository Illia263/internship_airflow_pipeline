"""Те, що зараз працює в проді. Автор — стажер, якого вже немає.

НЕ ПЕРЕПИСУЙ З НУЛЯ. Читай README.md.
"""

import csv
from datetime import datetime
from decimal import Decimal
import requests
import json
from tenacity import retry, wait_random_exponential, retry_if_exception_type, stop_after_attempt
import tempfile
import pendulum
from airflow.sdk import ObjectStoragePath, dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
import logging


logger = logging.getLogger(__name__)

@dag(
    dag_id="taxi_data",
    schedule="@monthly",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    end_date=pendulum.datetime(2024,12,31, tz="UTC"),
    catchup=False,
    tags=["taxi", "2024"]
)
def taxi_pipeline():
    
    @task
    @retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(3), retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError)), reraise=True)
    def download(target_month ):
        url = f"http://localhost:8000/yellow_tripdata_{target_month}.csv"
        r = requests.get(url)
        r.raise_for_status()
        base_dir = ObjectStoragePath("file:///tmp/taxi_data/")
        file_path = base_dir / f"yellow_tripdata_{target_month}.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as f:
            f.write(r.content)
        return file_path


    @task
    def load(input_path, target_month):
        hook = PostgresHook(postgres_conn_id="internship_airflow_pipeline")
        DB = hook.get_conn()
        logger.info(f"load_started, path={input_path}")
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
                    logger.warning(f"row_parsing_failed, reason={str(e)}, vendor_id = {r.get('VendorID')}")
                    yield("bad", {'raw-data' : r, 'reason' : str(e)})


        
        with input_path.open('r', encoding='utf-8') as raw_f, open("dead-letter.ndjson", 'a', encoding='utf-8') as dead_letter, tempfile.TemporaryFile("w+", newline='',  encoding='utf8') as temp_csv:
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
            logger.error(f"More than 5'%' of broken rows, total_loaded = {total_rows - error_count}, error_count={error_count}")
            DB.rollback()
            raise RuntimeError("More than 5'%' of broken rows")
            
                
        DB.commit()
        return total_rows - error_count
    current_month = "{{data_interval_start.format('YYYY-MM')}}" 
    downloaded_file = download(target_month=current_month)
    load(input_path=downloaded_file, target_month=current_month)




taxi_pipeline()