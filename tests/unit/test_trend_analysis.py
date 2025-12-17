import unittest
from collections import deque
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.monitor import ContainerMonitor

class TestTrendAnalysis(unittest.TestCase):
    def setUp(self):
        self.monitor = ContainerMonitor()
        # Mock config
        self.monitor.config = MagicMock()
        self.monitor.config.containers = []
        
    @patch('watchdog.monitor.datetime')
    def test_trend_analysis_slope(self, mock_datetime):
        """Test memory leak detection slope calculation"""
        container_name = "test-container"
        self.monitor.stats_history[container_name] = deque(maxlen=10)
        
        # Setup time sequence
        base_time = datetime(2025, 1, 1, 12, 0, 0)
        
        # We want _check_trend to be called multiple times to build history
        # Call 1: T0, 100MB
        mock_datetime.now.return_value = base_time
        self.monitor._check_trend(container_name, 100.0, 40.0)
        
        # Call 2: T1 (+1 min), 120MB
        mock_datetime.now.return_value = base_time + timedelta(minutes=1)
        self.monitor._check_trend(container_name, 120.0, 45.0)
        
        # Call 3: T2 (+2 min), 140MB -> Should trigger
        mock_datetime.now.return_value = base_time + timedelta(minutes=2)
        
        # Mock _report_issue to verify it's called
        self.monitor._report_issue = MagicMock()
        
        # Run check (memory_percent=60 > 50 threshold)
        self.monitor._check_trend(container_name, 140.0, 60.0)
        
        # Verify
        self.monitor._report_issue.assert_called_with(container_name, "MEMORY_LEAK_SUSPECTED")
        
    def test_trend_analysis_no_leak(self):
        """Test stable memory does not trigger leak detection"""
        container_name = "stable-container"
        self.monitor.stats_history[container_name] = deque(maxlen=10)
        history = self.monitor.stats_history[container_name]
        
        base_time = datetime.now()
        history.append((base_time, 100.0))
        history.append((base_time + timedelta(minutes=1), 102.0))
        history.append((base_time + timedelta(minutes=2), 101.0))
        
        self.monitor._report_issue = MagicMock()
        
        self.monitor._check_trend(container_name, 101.0, 40.0)
        
        self.monitor._report_issue.assert_not_called()

if __name__ == '__main__':
    unittest.main()
