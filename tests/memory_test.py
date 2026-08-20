import tracemalloc
import subprocess

def test_memory():
    tracemalloc.start()
    result = subprocess.run(['python', 'etl.py', '--backfill', '2024-01:2024-12'])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak /= 1024 * 1024
    assert result.returncode == 0
    assert peak < 500, f"Спожито забагто пам'яті ({peak})"
