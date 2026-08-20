import psycopg2
from decimal import Decimal

def test_money_inc():
    conn = psycopg2.connect("dbname=taxi user=postgres password=postgres host=localhost")
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE TEMP TABLE test_money_inc (val NUMERIC);")
        cursor.execute("INSERT INTO test_money_inc VALUES ('0.1'), ('0.2');")
        cursor.execute("SELECT SUM(val) FROM test_money_inc;")
        total = cursor.fetchone()[0]
        assert total == Decimal('0.3'), f"Помилка при знаходженні суми, отримано {total}"
    finally:
        conn.rollback()
        conn.close()