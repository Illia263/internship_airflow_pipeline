import psycopg2
def test_sql_injection():
    conn = psycopg2.connect("dbname=taxi user=postgres password=postgres host=localhost")
    cursor = conn.cursor()
    injection = "2024-01-01 00:00:00'; DROP TABLE trips; --"
    try:
        cursor.execute(
            """INSERT  INTO trips (vendor, pickup, dist, total)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT DO NOTHING;""",
               (1, injection, 1.5, 20.0)
        )
    except Exception as e:
        error = str(e).lower()
        assert "syntax error" not in error, 'Синтаксична помилка, можливо це інʼєкція'
    finally:
        conn.rollback()
        conn.close()    