import subprocess
import os

def test_logs():
    result = subprocess.run(['python', 'etl.py', '--month', '2024-05'],capture_output=True, text=True)
    assert len(result.stdout) > 0