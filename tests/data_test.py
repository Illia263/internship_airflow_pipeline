import subprocess
import psycopg2
def test_data():
    subprocess.run(['python', 'etl.py', '--month', '2024-01'])
    connect = psycopg2.connect("dbname=taxi user=postgres password=postgres host=localhost")
    with connect.cursor() as cursor:
        cursor.execute("SELECT DISTINCT to_char(pickup, 'YYYY-MM') FROM trips;")
        months = cursor.fetchall()
        assert len(months) == 1