import subprocess
import os
import psycopg2

def test_dead_letter():
    subprocess.run(['python', 'etl.py', '--month', '2024-06-broken'])
    
    assert os.path.exists("dead-letter.ndjson"), "Файлу dead letter немає"
    assert os.path.getsize("dead-letter.ndjson") > 0, "Файл пустий"
    os.remove('dead-letter.ndjson')
def test_five_percent():
    conn = psycopg2.connect("dbname=taxi user=postgres password=postgres host=localhost")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trips;")
    count_before = cursor.fetchone()[0]

    result = subprocess.run(['python', 'etl.py', '--month', '2024-06-broken'])
    
    assert result.returncode == 1, f"{result.returncode}"
    cursor.execute("SELECT COUNT(*) FROM trips;")
    count_after = cursor.fetchone()[0]
    assert count_after == count_before, "лишні рядки засмітили бд"

