import subprocess
def test_invalid_inc2():
    result= subprocess.run(['python', 'etl.py'], capture_output=True, text=True)
    assert result.returncode != 0

def test_month_inc2():
    result = subprocess.run(['python', 'etl.py', '--month', '2024-01'], capture_output=True, text=True)
    assert result.returncode == 0
def test_backfill_inc2():
    result = subprocess.run(['python', 'etl.py', '--backfill', '2024-01:2024-04'], capture_output=True, text=True)
    assert result.returncode == 0