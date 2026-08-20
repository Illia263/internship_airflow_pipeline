import subprocess

def test_exit_2():
    result = subprocess.run(['python', 'etl.py'])
    assert result.returncode == 2
def test_exit_1():
    result = subprocess.run(['python', 'etl.py', '--month', '2024-06-broken'])
    assert result.returncode == 1
def test_exit_0():
    result = subprocess.run(['python', 'etl.py', '--month', '2024-06'])
    assert result.returncode == 0

def test_HTTP_error():
    result = subprocess.run(['python', 'etl.py', '--month', '2024-13'], capture_output=True, text=True)
    assert result.returncode == 2
    
    attemps = result.stdout.count("download_started")
    assert attemps == 3