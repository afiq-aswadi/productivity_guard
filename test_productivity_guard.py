import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import base64
from datetime import datetime
from PIL import Image
import io
import json
import numpy as np

# Add the parent directory to the path so we can import productivity_guard
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from productivity_guard import ProductivityGuard


class TestProductivityGuard(unittest.TestCase):
    """Comprehensive test suite for ProductivityGuard."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'OPENROUTER_API_KEY': 'test-api-key',
            'CHECK_INTERVAL': '120',
            'MEDIUM_MODEL': 'test-medium-model',
            'BEST_MODEL': 'test-best-model',
            'OPENROUTER_APP_NAME': 'test-app'
        })
        self.env_patcher.start()
        
        # Mock LLMClient
        self.llm_client_patcher = patch('llm_utils.LLMClient')
        self.mock_llm_client_class = self.llm_client_patcher.start()
        self.mock_llm_client = Mock()
        self.mock_llm_client_class.return_value = self.mock_llm_client
        
        # Mock mss
        self.mss_patcher = patch('productivity_guard.mss')
        self.mock_mss_class = self.mss_patcher.start()
        self.mock_sct = Mock()
        self.mock_mss_class.return_value = self.mock_sct
        
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        self.llm_client_patcher.stop()
        self.mss_patcher.stop()
    
    def test_init_default_values(self):
        """Test ProductivityGuard initialization with default values."""
        guard = ProductivityGuard()
        
        self.assertEqual(guard.interval, 120)
        self.assertFalse(guard.debug)
        self.assertIsNotNone(guard.client)
        self.assertIsNotNone(guard.sct)
        self.assertEqual(guard.previous_screenshots, {})
        self.assertEqual(guard.last_description, "")
        self.assertEqual(guard.productivity_exceptions, [])
        self.assertFalse(guard.stop_monitoring)
    
    def test_init_debug_mode(self):
        """Test ProductivityGuard initialization in debug mode."""
        guard = ProductivityGuard(debug=True)
        
        self.assertEqual(guard.interval, 10)  # Should be 10 in debug mode
        self.assertTrue(guard.debug)
        self.assertTrue(hasattr(guard, 'debug_dir'))
    
    def test_init_custom_interval(self):
        """Test ProductivityGuard initialization with custom interval."""
        guard = ProductivityGuard(interval=300)
        
        self.assertEqual(guard.interval, 300)
    
    def test_debug_log_enabled(self):
        """Test debug_log when debug mode is enabled."""
        guard = ProductivityGuard(debug=True)
        
        with patch('builtins.print') as mock_print:
            guard.debug_log("Test message", {"key": "value"})
            
            # Should print both message and data
            self.assertEqual(mock_print.call_count, 2)
            call_args = [call[0][0] for call in mock_print.call_args_list]
            self.assertTrue(any("Test message" in arg for arg in call_args))
            self.assertTrue(any("key" in arg for arg in call_args))
    
    def test_debug_log_disabled(self):
        """Test debug_log when debug mode is disabled."""
        guard = ProductivityGuard(debug=False)
        
        with patch('builtins.print') as mock_print:
            guard.debug_log("Test message", {"key": "value"})
            
            # Should not print anything
            mock_print.assert_not_called()
    
    def test_debug_log_truncate_long_string(self):
        """Test debug_log truncates long string data."""
        guard = ProductivityGuard(debug=True)
        
        long_string = "x" * 200
        with patch('builtins.print') as mock_print:
            guard.debug_log("Test", long_string)
            
            call_args = [call[0][0] for call in mock_print.call_args_list]
            self.assertTrue(any("truncated" in arg for arg in call_args))
    
    def test_process_image_resize(self):
        """Test process_image resizes large images."""
        guard = ProductivityGuard()
        
        # Create a large test image
        img = Image.new('RGB', (1600, 1200), color='red')
        
        processed_img = guard.process_image(img, max_width=800)
        
        self.assertEqual(processed_img.width, 800)
        self.assertEqual(processed_img.height, 600)  # Should maintain aspect ratio
    
    def test_process_image_no_resize_needed(self):
        """Test process_image doesn't resize small images."""
        guard = ProductivityGuard()
        
        # Create a small test image
        img = Image.new('RGB', (400, 300), color='blue')
        
        processed_img = guard.process_image(img, max_width=800)
        
        self.assertEqual(processed_img.width, 400)
        self.assertEqual(processed_img.height, 300)
    
    @patch('productivity_guard.OCR_AVAILABLE', True)
    @patch('productivity_guard.OCR_TYPE', 'easyocr')
    def test_extract_text_easyocr(self):
        """Test text extraction with EasyOCR."""
        guard = ProductivityGuard()
        
        # Mock OCR reader
        mock_reader = Mock()
        mock_reader.readtext.return_value = [
            (None, "Hello", None),
            (None, "World", None)
        ]
        guard.ocr_reader = mock_reader
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='white')
        
        text = guard.extract_text_from_image(img)
        
        self.assertEqual(text, "Hello World")
        mock_reader.readtext.assert_called_once()
    
    @patch('productivity_guard.OCR_AVAILABLE', True)
    @patch('productivity_guard.OCR_TYPE', 'pytesseract')
    @patch('productivity_guard.pytesseract')
    def test_extract_text_pytesseract(self, mock_pytesseract):
        """Test text extraction with PyTesseract."""
        guard = ProductivityGuard()
        
        mock_pytesseract.image_to_string.return_value = "Hello\nWorld"
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='white')
        
        text = guard.extract_text_from_image(img)
        
        self.assertEqual(text, "Hello\nWorld")
        mock_pytesseract.image_to_string.assert_called_once()
    
    @patch('productivity_guard.OCR_AVAILABLE', False)
    def test_extract_text_no_ocr(self):
        """Test text extraction when OCR is not available."""
        guard = ProductivityGuard()
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='white')
        
        text = guard.extract_text_from_image(img)
        
        self.assertEqual(text, "")
    
    def test_take_screenshot_multiple_monitors(self):
        """Test taking screenshots from multiple monitors."""
        guard = ProductivityGuard()
        
        # Mock monitor configuration
        mock_monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 1920, "top": 0, "width": 1920, "height": 1080}
        ]
        guard.sct.monitors = mock_monitors
        
        # Mock screenshot data
        mock_img_data = b"fake_image_data"
        mock_sct_img = Mock()
        mock_sct_img.rgb = mock_img_data
        guard.sct.grab.return_value = mock_sct_img
        
        with patch('productivity_guard.Image.frombytes') as mock_frombytes:
            mock_pil_img = Mock()
            mock_frombytes.return_value = mock_pil_img
            
            screenshots = guard.take_screenshot()
        
        self.assertEqual(len(screenshots), 2)
        self.assertEqual(guard.sct.grab.call_count, 2)
    
    def test_take_screenshot_error_handling(self):
        """Test screenshot error handling."""
        guard = ProductivityGuard()
        
        # Mock monitor configuration
        guard.sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        
        # Make grab raise an exception
        guard.sct.grab.side_effect = Exception("Screenshot failed")
        
        with patch('builtins.print') as mock_print:
            screenshots = guard.take_screenshot()
        
        self.assertEqual(screenshots, [])
        mock_print.assert_called_with("Error taking screenshots: Screenshot failed")
    
    def test_check_with_model_cached_result(self):
        """Test _check_with_model returns cached results."""
        guard = ProductivityGuard()
        
        # Create test screenshots
        img1 = Image.new('RGB', (100, 100), color='red')
        img2 = Image.new('RGB', (100, 100), color='blue')
        screenshots = [img1, img2]
        
        # Pre-populate cache
        guard.previous_screenshots["test_cache_key"] = (True, "Cached response")
        
        # Mock hash calculation to return our test key
        with patch('productivity_guard.hashlib.md5') as mock_md5:
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "test_cache_key"
            mock_md5.return_value = mock_hash
            
            result, response = guard._check_with_model(screenshots, None, "test-model")
        
        self.assertTrue(result)
        self.assertEqual(response, "Cached response")
        # LLM should not be called
        self.mock_llm_client.chat.assert_not_called()
    
    def test_check_with_model_api_call(self):
        """Test _check_with_model makes API call for new screenshots."""
        guard = ProductivityGuard()
        
        # Create test screenshots
        img1 = Image.new('RGB', (100, 100), color='red')
        screenshots = [img1]
        
        # Mock LLM response
        self.mock_llm_client.chat.return_value = {
            "content": "The user is browsing social media.\nYes"
        }
        
        result, response = guard._check_with_model(screenshots, None, "test-model")
        
        self.assertTrue(result)
        self.assertIn("browsing social media", response)
        self.mock_llm_client.chat.assert_called_once()
    
    def test_check_with_model_reasoning(self):
        """Test _check_with_model with reasoning enabled."""
        guard = ProductivityGuard()
        
        # Create test screenshots
        img1 = Image.new('RGB', (100, 100), color='red')
        screenshots = [img1]
        
        # Mock LLM response
        self.mock_llm_client.chat.return_value = {
            "content": "Working on code.\nNo"
        }
        
        result, response = guard._check_with_model(
            screenshots, None, "test-pro-model", use_reasoning=True
        )
        
        self.assertFalse(result)
        # Check that reasoning was passed to the API
        call_args = self.mock_llm_client.chat.call_args[1]
        self.assertTrue(call_args.get('reasoning'))
    
    def test_check_procrastination_two_step(self):
        """Test the two-step procrastination check process."""
        guard = ProductivityGuard()
        
        # Create test screenshots
        img1 = Image.new('RGB', (100, 100), color='red')
        screenshots = [img1]
        
        # First call (Flash) returns True (procrastinating)
        # Second call (Pro) returns False (not procrastinating)
        self.mock_llm_client.chat.side_effect = [
            {"content": "User is on Reddit.\nYes"},
            {"content": "User is researching for work.\nNo"}
        ]
        
        with patch('builtins.print'):
            result = guard.check_procrastination(screenshots)
        
        self.assertFalse(result)  # Pro's decision is final
        self.assertEqual(self.mock_llm_client.chat.call_count, 2)
    
    def test_check_procrastination_flash_says_no(self):
        """Test when Flash says not procrastinating, skip Pro check."""
        guard = ProductivityGuard()
        
        # Create test screenshots
        img1 = Image.new('RGB', (100, 100), color='red')
        screenshots = [img1]
        
        # Flash returns False (not procrastinating)
        self.mock_llm_client.chat.return_value = {
            "content": "User is coding.\nNo"
        }
        
        with patch('builtins.print'):
            result = guard.check_procrastination(screenshots)
        
        self.assertFalse(result)
        self.assertEqual(self.mock_llm_client.chat.call_count, 1)  # Only Flash called
    
    @patch('sys.platform', 'darwin')
    @patch('subprocess.run')
    def test_bring_terminal_to_front_macos(self, mock_run):
        """Test bringing terminal to front on macOS."""
        guard = ProductivityGuard()
        
        guard.bring_terminal_to_front()
        
        # Should play sound and run AppleScript
        self.assertTrue(any(
            'afplay' in str(call) for call in mock_run.call_args_list
        ))
        self.assertTrue(any(
            'osascript' in str(call) for call in mock_run.call_args_list
        ))
    
    @patch('sys.platform', 'win32')
    def test_bring_terminal_to_front_windows(self):
        """Test bringing terminal to front on Windows."""
        guard = ProductivityGuard()
        
        # Windows implementation would go here
        # For now, just test it doesn't crash
        guard.bring_terminal_to_front()
    
    def test_start_intervention(self):
        """Test intervention mode."""
        guard = ProductivityGuard()
        guard.last_description = "User is on social media"
        
        # Mock LLM responses
        self.mock_llm_client.chat.side_effect = [
            {"content": "Let's get back to work!"},
            {"content": "Great! What were you working on?"}
        ]
        
        # Mock user input
        with patch('builtins.input', side_effect=["I was just taking a break", "exit"]):
            with patch('builtins.print'):
                guard.start_intervention()
        
        self.assertEqual(self.mock_llm_client.chat.call_count, 2)
    
    def test_wait_with_input_check(self):
        """Test wait_with_input_check method."""
        guard = ProductivityGuard()
        
        # Test with no input
        guard.input_queue.empty = Mock(return_value=True)
        
        with patch('time.sleep') as mock_sleep:
            guard.wait_with_input_check(2)
            
        # Should sleep for the full duration
        total_sleep = sum(call[0][0] for call in mock_sleep.call_args_list)
        self.assertAlmostEqual(total_sleep, 2, places=1)
    
    def test_wait_with_input_check_interrupted(self):
        """Test wait_with_input_check with input interruption."""
        guard = ProductivityGuard()
        
        # Mock input queue to return a command
        guard.input_queue.empty = Mock(side_effect=[True, True, False])
        guard.input_queue.get = Mock(return_value="test_command")
        
        with patch('time.sleep'):
            guard.wait_with_input_check(5)
        
        # Should have gotten the command
        guard.input_queue.get.assert_called_once()
    
    @patch('productivity_guard.threading.Thread')
    def test_run_main_loop(self, mock_thread):
        """Test the main run loop."""
        guard = ProductivityGuard()
        
        # Mock components
        guard.take_screenshot = Mock(side_effect=[
            [Mock()],  # First iteration
            [Mock()],  # Second iteration
            KeyboardInterrupt()  # Stop the loop
        ])
        guard.check_procrastination = Mock(return_value=False)
        
        with patch('builtins.print'):
            guard.run()
        
        # Should have started input thread
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
        
        # Should have taken screenshots twice before KeyboardInterrupt
        self.assertEqual(guard.take_screenshot.call_count, 3)
        self.assertEqual(guard.check_procrastination.call_count, 2)
    
    def test_run_with_procrastination_detected(self):
        """Test run loop when procrastination is detected."""
        guard = ProductivityGuard()
        
        # Mock components
        guard.take_screenshot = Mock(side_effect=[
            [Mock()],  # First iteration
            KeyboardInterrupt()  # Stop after first check
        ])
        guard.check_procrastination = Mock(return_value=True)
        guard.bring_terminal_to_front = Mock()
        guard.start_intervention = Mock()
        
        with patch('productivity_guard.threading.Thread'):
            with patch('builtins.print'):
                guard.run()
        
        # Should have triggered intervention
        guard.bring_terminal_to_front.assert_called_once()
        guard.start_intervention.assert_called_once()
    
    def test_save_debug_screenshot(self):
        """Test saving debug screenshots."""
        guard = ProductivityGuard(debug=True)
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='green')
        
        with patch('productivity_guard.Image.Image.save') as mock_save:
            guard.save_debug_screenshot(img, 1)
            
        mock_save.assert_called_once()
        save_path = mock_save.call_args[0][0]
        self.assertIn('monitor_1', save_path)
        self.assertIn('.png', save_path)


class TestIntegration(unittest.TestCase):
    """Integration tests for ProductivityGuard."""
    
    @patch('productivity_guard.LLMClient')
    @patch('productivity_guard.mss')
    @patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-key'})
    def test_full_monitoring_cycle(self, mock_mss, mock_llm_client_class):
        """Test a complete monitoring cycle."""
        # Setup mocks
        mock_client = Mock()
        mock_llm_client_class.return_value = mock_client
        
        mock_sct = Mock()
        mock_mss.return_value = mock_sct
        
        # Mock monitors
        mock_sct.monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080}
        ]
        
        # Mock screenshot
        mock_img_data = b"\\x00" * (1920 * 1080 * 3)
        mock_sct_img = Mock()
        mock_sct_img.rgb = mock_img_data
        mock_sct.grab.return_value = mock_sct_img
        
        # Mock LLM responses
        mock_client.chat.return_value = {"content": "User is working.\nNo"}
        
        # Create guard and run one iteration
        guard = ProductivityGuard()
        
        # Take screenshot
        screenshots = guard.take_screenshot()
        self.assertEqual(len(screenshots), 1)
        
        # Check procrastination
        with patch('builtins.print'):
            result = guard.check_procrastination(screenshots)
        
        self.assertFalse(result)
        mock_client.chat.assert_called()


if __name__ == '__main__':
    unittest.main()