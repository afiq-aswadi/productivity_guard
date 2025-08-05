#!/usr/bin/env python3
"""
Test script for the break feature functionality.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import queue

# Import the ProductivityGuard class
from productivity_guard import ProductivityGuard

class TestBreakFeature(unittest.TestCase):
    """Test cases for break functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock ProductivityGuard instance with minimal initialization
        with patch('productivity_guard.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 8, 4, 9, 0, 0)
            with patch('builtins.open'), \
                 patch('os.makedirs'), \
                 patch('os.path.exists', return_value=True):
                self.guard = ProductivityGuard(
                    debug=False, 
                    test_mode=True, 
                    interval=5, 
                    disable_sound=True
                )
    
    def test_break_initialization(self):
        """Test that break state is properly initialized."""
        self.assertFalse(self.guard.on_break)
        self.assertIsNone(self.guard.break_start_time)
        self.assertEqual(self.guard.break_duration, 0)
        self.assertEqual(self.guard.break_activity, "")
    
    @patch('builtins.input', return_value='taking a walk')
    @patch('productivity_guard.ProductivityGuard.get_break_advice')
    @patch('productivity_guard.ProductivityGuard.log_activity_to_file')
    def test_start_break(self, mock_log, mock_advice, mock_input):
        """Test starting a break."""
        with patch('productivity_guard.datetime') as mock_dt:
            mock_now = datetime(2025, 8, 4, 10, 0, 0)
            mock_dt.now.return_value = mock_now
            
            # Start a 15-minute break
            self.guard.start_break(15)
            
            # Verify break state
            self.assertTrue(self.guard.on_break)
            self.assertEqual(self.guard.break_start_time, mock_now)
            self.assertEqual(self.guard.break_duration, 15 * 60)  # 15 minutes in seconds
            self.assertEqual(self.guard.break_activity, "taking a walk")
            
            # Verify advice was requested
            mock_advice.assert_called_once_with("taking a walk", 15)
            
            # Verify activity was logged
            mock_log.assert_called_once_with("BREAKS", "Started 15-minute break: taking a walk")
    
    def test_start_break_when_already_on_break(self):
        """Test that starting a break when already on break shows status."""
        self.guard.on_break = True
        self.guard.break_start_time = datetime.now()
        self.guard.break_duration = 10 * 60
        self.guard.break_activity = "existing break"
        
        with patch('productivity_guard.ProductivityGuard.show_break_status') as mock_status:
            self.guard.start_break(15)
            mock_status.assert_called_once()
    
    def test_show_break_status_when_not_on_break(self):
        """Test showing break status when not on break."""
        with patch('builtins.print') as mock_print:
            self.guard.show_break_status()
            mock_print.assert_called_with("☕ No active break.")
    
    def test_show_break_status_when_on_break(self):
        """Test showing break status when on break."""
        with patch('productivity_guard.datetime') as mock_dt:
            start_time = datetime(2025, 8, 4, 10, 0, 0)
            current_time = datetime(2025, 8, 4, 10, 5, 0)  # 5 minutes elapsed
            mock_dt.now.return_value = current_time
            
            self.guard.on_break = True
            self.guard.break_start_time = start_time
            self.guard.break_duration = 15 * 60  # 15 minutes
            self.guard.break_activity = "taking a walk"
            
            with patch('builtins.print') as mock_print:
                self.guard.show_break_status()
                
                # Check that status information was printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                self.assertTrue(any("BREAK MODE ACTIVE" in call for call in print_calls))
                self.assertTrue(any("taking a walk" in call for call in print_calls))
                self.assertTrue(any("10:00" in call for call in print_calls))  # 10 minutes remaining
    
    @patch('productivity_guard.ProductivityGuard.log_activity_to_file')
    def test_check_break_timer_completion(self, mock_log):
        """Test break timer completion."""
        with patch('productivity_guard.datetime') as mock_dt:
            start_time = datetime(2025, 8, 4, 10, 0, 0)
            end_time = datetime(2025, 8, 4, 10, 15, 0)  # 15 minutes later
            mock_dt.now.return_value = end_time
            
            self.guard.on_break = True
            self.guard.break_start_time = start_time
            self.guard.break_duration = 15 * 60  # 15 minutes
            self.guard.break_activity = "taking a walk"
            
            with patch('builtins.print'):
                result = self.guard.check_break_timer()
                
                # Verify break ended
                self.assertTrue(result)
                self.assertFalse(self.guard.on_break)
                self.assertEqual(self.guard.break_activity, "")
                
                # Verify completion was logged
                mock_log.assert_called_once_with("PLANNING", "Break ended - resumed work after 15 minutes")
    
    def test_check_break_timer_still_active(self):
        """Test break timer when still active."""
        with patch('productivity_guard.datetime') as mock_dt:
            start_time = datetime(2025, 8, 4, 10, 0, 0)
            current_time = datetime(2025, 8, 4, 10, 5, 0)  # 5 minutes elapsed
            mock_dt.now.return_value = current_time
            
            self.guard.on_break = True
            self.guard.break_start_time = start_time
            self.guard.break_duration = 15 * 60  # 15 minutes
            self.guard.break_activity = "taking a walk"
            
            result = self.guard.check_break_timer()
            
            # Verify break is still active
            self.assertFalse(result)
            self.assertTrue(self.guard.on_break)
    
    @patch('productivity_guard.ProductivityGuard.call_openrouter_api')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open')
    def test_get_break_advice(self, mock_open, mock_exists, mock_api):
        """Test getting AI advice for break activity."""
        # Mock file reading
        mock_file = MagicMock()
        mock_file.read.return_value = "Test prompt with {break_activity} and {break_duration}"
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock API response
        mock_api.return_value = "Great choice for your break!"
        
        with patch('builtins.print') as mock_print:
            self.guard.get_break_advice("taking a walk", 15)
            
            # Verify API was called
            mock_api.assert_called_once()
            
            # Verify advice was printed
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            self.assertTrue(any("AI Break Coach says:" in call for call in print_calls))

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)