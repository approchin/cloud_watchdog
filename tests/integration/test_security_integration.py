import pytest
import subprocess
import time
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.security import check_logs_for_injection, check_processes
from watchdog.evidence import get_container_logs
from watchdog.executor import execute_action

TEST_CONTAINER_NAME = "watchdog-security-test"

@pytest.fixture(scope="module")
def security_container():
    """
    Fixture to start a container for security testing.
    It prints a malicious log line and sleeps.
    """
    # 1. Start container
    # We use alpine and print a SQL injection log, then sleep
    cmd = [
        "docker", "run", "-d", "--name", TEST_CONTAINER_NAME,
        "alpine", "sh", "-c", 
        "echo 'ERROR: SQL syntax error near UNION SELECT * FROM users'; sleep 300"
    ]
    subprocess.run(cmd, check=True)
    
    # Wait for container to be ready
    time.sleep(2)
    
    yield TEST_CONTAINER_NAME
    
    # Teardown: Stop and remove
    subprocess.run(["docker", "rm", "-f", TEST_CONTAINER_NAME], capture_output=True)
    
    # Cleanup any forensics images
    subprocess.run("docker rmi $(docker images -q forensics_watchdog-security-test*)", shell=True, capture_output=True)

def test_log_injection_detection(security_container):
    """Test detection of SQL injection patterns in logs"""
    logs = get_container_logs(security_container)
    patterns = check_logs_for_injection(logs)
    assert patterns is not None
    assert "UNION SELECT" in patterns[0] or "UNION SELECT" in str(patterns)

def test_process_detection(security_container):
    """
    Test detection of malicious processes.
    Since we can't easily start a real miner, we'll mock the check_processes 
    function's internal list or try to simulate a process name if possible.
    
    Actually, let's try to start a process with a suspicious name inside the container.
    """
    # Create a script named 'xmrig' (common miner name)
    setup_cmd = f"docker exec {security_container} sh -c 'echo \"sleep 10\" > /xmrig && chmod +x /xmrig && ./xmrig &'"
    subprocess.run(setup_cmd, shell=True)
    
    time.sleep(1)
    
    procs = check_processes(security_container)
    assert procs is not None
    assert "xmrig" in procs

def test_commit_forensics(security_container):
    """Test the COMMIT action (Forensics)"""
    # Execute COMMIT action
    result = execute_action("COMMIT", security_container)
    
    assert result["success"] is True
    assert result["action"] == "COMMIT"
    assert result["image_name"] is not None
    assert "forensics_" in result["image_name"]
    
    # Verify image exists
    img_check = subprocess.run(
        ["docker", "inspect", result["image_name"]],
        capture_output=True
    )
    assert img_check.returncode == 0
    
    # Verify runtime dump file exists in the image
    # We run a quick command in the new image to check /tmp/forensics_dump.txt
    verify_cmd = [
        "docker", "run", "--rm", result["image_name"],
        "ls", "/tmp/forensics_dump.txt"
    ]
    verify = subprocess.run(verify_cmd, capture_output=True)
    assert verify.returncode == 0
