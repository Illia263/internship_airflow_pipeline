import subprocess
import time

def test_speed():
    start_time = time.perf_counter()
    result = subprocess.run(['python', 'etl.py', '--month', '2024-03'])
    end_time = time.perf_counter()
    duration = end_time - start_time
    assert duration < 60