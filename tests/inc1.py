import subprocess
import psycopg2

def test_idempotency_row_cout():
    subprocess.run(['python', 'etl.py', '--month', '2024-01'], capture_output=True, text=True)
    conn = psycopg2.connect("dbname=taxi user=postgres password=postgres host=localhost")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trips;")
    count_first_run = cursor.fetchone()[0]

    subprocess.run(['python', 'etl.py', '--month', '2024-01'], capture_output=True, text=True)
    cursor.execute("SELECT COUNT(*) FROM trips;")
    count_second_run = cursor.fetchone()[0]
    conn.close()
    assert count_first_run == count_second_run, "Дані здублювались"

