#!/usr/bin/env python3
"""
End-to-End Full Lifecycle Test
==============================

This test suite verifies the complete lifecycle of the Cloud Watchdog system,
from detection to action, using real Docker containers and the real Agent logic.

Scenarios:
1. Security Incident (Level 2): Malicious process -> Detection -> Agent -> COMMIT + STOP
2. Crash Loop: Repeated crashes -> Detection -> Agent -> STOP
3. Resource Stress: High CPU -> Detection -> Agent -> ALERT/RESTART

Prerequisites:
- Docker and Docker Compose installed
- DeepSeek API Key configured
"""
import sys
import os
import time
import pytest
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.config import init_config
from watchdog.monitor import ContainerMonitor
from watchdog.evidence import get_container_info

# Constants
COMPOSE_FILE = "docker-compose.extended.yml"
SECURITY_CONTAINER = "security-simulation"
CRASH_CONTAINER = "crash-loop"

@pytest.fixture(scope="module")
def test_environment():
    """
    Setup and Teardown of the test environment.
    Starts all test containers before tests, and cleans up after.
    """
    print("\n[Setup] Starting test environment...")
    # Build and start containers
    subprocess.run(
        ["docker-compose", "-f", COMPOSE_FILE, "up", "-d", "--build"],
        cwd=os.path.join(os.getcwd(), "test-containers"),
        check=True
    )
    
    # Wait for containers to stabilize
    time.sleep(10)
    
    # Initialize config
    init_config()
    
    yield
    
    print("\n[Teardown] Stopping test environment...")
    subprocess.run(
        ["docker-compose", "-f", COMPOSE_FILE, "down"],
        cwd=os.path.join(os.getcwd(), "test-containers"),
        check=True
    )
    
    # Cleanup forensics images
    subprocess.run("docker rmi $(docker images -q forensics_*)", shell=True, capture_output=True)

def wait_for_container_status(container_name, status, timeout=30):
    """Wait for a container to reach a specific status (running/exited)"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        info = get_container_info(container_name)
        if status == "running" and info and info.get("running"):
            return True
        if status == "exited" and (not info or not info.get("running")):
            return True
        time.sleep(1)
    return False

class TestFullLifecycle:
    
    def test_security_incident_response(self, test_environment):
        """
        Scenario: Security Simulation Container runs a malicious process.
        Expectation: Watchdog detects it, Agent decides COMMIT, Executor commits and stops it.
        """
        print(f"\n[Test] Testing Security Incident Response for {SECURITY_CONTAINER}")
        
        # 1. Ensure container is running initially
        # Note: It might have been stopped by previous runs if not cleaned up, 
        # but the fixture 'up -d' should have started it.
        subprocess.run(["docker", "start", SECURITY_CONTAINER], capture_output=True)
        assert wait_for_container_status(SECURITY_CONTAINER, "running"), "Container failed to start"
        
        # 2. Initialize Monitor (but don't start the infinite loop threads)
        monitor = ContainerMonitor()
        
        # 3. Trigger Security Check manually
        # The container takes a few seconds to start the malicious process (sleep 1 in script)
        time.sleep(5) 
        
        print(f"[Action] Triggering security check for {SECURITY_CONTAINER}")
        start_time = time.time()
        # We call the internal method to simulate the loop hitting this container
        monitor._check_security(SECURITY_CONTAINER)
        
        # 4. Wait for Agent to process (Agent runs in background thread started by Monitor init?)
        # Monitor init does NOT start agent threads. Monitor._report_issue starts them if needed?
        # Let's check monitor.py: _report_issue calls self.agent.submit_task
        # We need to make sure the Agent's TaskQueue is running.
        # Monitor.__init__ initializes DiagnosisAgent but doesn't start the queue thread explicitly?
        # Actually, DiagnosisAgent starts TaskQueue on init.
        
        print("[Wait] Waiting for Agent to process task...")
        
        # Poll for status change instead of hard sleep to measure time
        is_stopped = False
        for _ in range(30): # Wait up to 30 seconds
            if wait_for_container_status(SECURITY_CONTAINER, "exited", timeout=1):
                is_stopped = True
                break
        
        end_time = time.time()
        duration = end_time - start_time
        print(f"[Metric] Security Response Time: {duration:.2f} seconds")

        # time.sleep(20) # Give LLM and Docker Commit some time (Commit takes time)
        
        # 5. Verify Outcome
        # Container should be stopped
        # is_stopped = wait_for_container_status(SECURITY_CONTAINER, "exited", timeout=10)
        assert is_stopped, f"Container {SECURITY_CONTAINER} should be stopped after security incident"
        
        # Image should exist
        result = subprocess.run(
            "docker images | grep forensics", 
            shell=True, capture_output=True, text=True
        )
        assert SECURITY_CONTAINER in result.stdout, "Forensics image was not created"
        print("[Success] Security incident handled correctly (Commit + Stop)")

    def test_crash_loop_response(self, test_environment):
        """
        Scenario: Crash Loop Container keeps dying.
        Expectation: Watchdog detects crash, Agent decides STOP (after threshold).
        """
        print(f"\n[Test] Testing Crash Loop Response for {CRASH_CONTAINER}")
        
        # 1. Ensure container is in crash loop state
        # It restarts automatically due to docker-compose restart policy?
        # Our config says 'auto_restart: true' in watchlist.yml
        
        monitor = ContainerMonitor()
        
        # 2. Simulate detection of "die" event or "not running" state
        # The container exits immediately with 137 or 1.
        
        # We simulate the monitor finding it dead
        print(f"[Action] Triggering liveness check for {CRASH_CONTAINER}")
        start_time = time.time()
        
        # We need to fake the restart count history to trigger the STOP decision immediately
        # otherwise we'd have to wait for 3 restarts.
        # In a real E2E, we should wait, but for speed we can inject history?
        # Or just run it 4 times.
        
        # Increase iterations and wait time to ensure we hit the threshold
        for i in range(6):
            print(f"  Iteration {i+1}...")
            # Check if alive (it should be dead or restarting)
            # _check_all_containers_alive calls _report_issue if dead
            monitor._check_all_containers_alive()
            
            # Check if it has stopped yet (break early if resolved)
            if wait_for_container_status(CRASH_CONTAINER, "exited", timeout=1):
                 # Double check it's not just between restarts - check if agent stopped it?
                 # But for E2E, if it stays exited, we are good.
                 pass
            
            time.sleep(2) # Reduced sleep to poll faster
        
        print("[Wait] Waiting for Agent to make final decision...")
        
        is_stopped = False
        for _ in range(20):
             if wait_for_container_status(CRASH_CONTAINER, "exited", timeout=1):
                 is_stopped = True
                 break
        
        end_time = time.time()
        duration = end_time - start_time
        print(f"[Metric] Crash Loop Response Time: {duration:.2f} seconds")

        # time.sleep(15)
        
        # 3. Verify Outcome
        # It should be stopped (and ideally removed from auto-restart by the Agent, 
        # but Docker's restart policy might fight back if not handled. 
        # Our Executor uses 'docker stop', which overrides restart policy usually).
        
        info = get_container_info(CRASH_CONTAINER)
        # If it's stopped, 'Running' is False.
        assert info is not None
        # Note: In some environments, docker stop might take time or restart policy might kick in immediately.
        # But our Agent logic is to STOP it.
        # If it failed, it might be because the Agent didn't trigger STOP or STOP failed.
        # Let's check if it's running.
        print(f"Container info: {info}")
        assert info['running'] is False, f"Container {CRASH_CONTAINER} should be stopped"
        print("[Success] Crash loop handled correctly (Stop)")

if __name__ == "__main__":
    # Allow running directly
    sys.exit(pytest.main(["-v", __file__]))
