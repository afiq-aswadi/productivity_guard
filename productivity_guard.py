import os
import time
import tempfile
from datetime import datetime, timedelta
from mss import mss
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import base64
import io
from PIL import Image
import argparse
import json
import shutil
import hashlib
import sys
import subprocess
from typing import Any, Dict, List
import threading
import queue
import numpy as np
import warnings

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", message=".*pin_memory.*")
warnings.filterwarnings("ignore", message=".*MPS.*")

# Fix pin_memory issue on Apple Silicon (MPS) for EasyOCR/PyTorch
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'
# Disable pin_memory on MPS to prevent UserWarning
os.environ['PYTORCH_DISABLE_PIN_MEMORY_ON_MPS'] = '1'

try:
    import easyocr
    OCR_AVAILABLE = True
    OCR_TYPE = "easyocr"
except ImportError:
    try:
        import pytesseract
        OCR_AVAILABLE = True
        OCR_TYPE = "pytesseract"
    except ImportError:
        OCR_AVAILABLE = False
        OCR_TYPE = None
if OCR_AVAILABLE:
    print(f"OCR available, {OCR_TYPE=}")
else:
    print("OCR not available")

def load_prompt(filename):
    """Load a prompt from the prompts directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', filename)
    try:
        with open(prompt_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: Prompt file {filename} not found in prompts/ directory")
        return ""

# Load prompts from files
detection_prompt = load_prompt('detection_prompt.md')
intervention_prompt = load_prompt('intervention_prompt.md')
activity_categorization_prompt = load_prompt('activity_categorization_prompt.md')
workday_summary_prompt = load_prompt('workday_summary_prompt.md')

# Add OCR note if available
ocr_note = (
    "\n\nNote: Text content from the screens has been extracted using OCR and will be provided separately to help with analysis. If there is no text content, ignore this note."
    if OCR_AVAILABLE
    else ""
)

# Update detection prompt with OCR note if needed
if OCR_AVAILABLE and ocr_note not in detection_prompt:
    detection_prompt = detection_prompt.replace(
        "IMPORTANT: These screenshots are from TWO MONITORS for the same user, so consider them together.",
        f"IMPORTANT: These screenshots are from TWO MONITORS for the same user, so consider them together.{ocr_note}"
    )

SYSTEM_PROMPT = detection_prompt

# Load environment variables
load_dotenv(find_dotenv())

class ProductivityGuard:
    def __init__(self, interval=None, debug=False, test_mode=False, disable_sound=False):
        """Initialize ProductivityGuard with a checking interval in seconds."""
        # LLMClient will automatically use OPENROUTER_API_KEY from environment

        # Get interval from environment or use default
        self.interval = interval or int(os.getenv('CHECK_INTERVAL', 120))
        if debug:
            self.interval = 10  # Override interval in debug mode
            
        # Sound notification settings
        self.disable_sound = disable_sound or os.getenv('DISABLE_SOUND', 'false').lower() == 'true'

        # Check for API key
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "No API key found. Please set OPENROUTER_API_KEY in your .env file.\n"
                "Get your API key from https://openrouter.ai/settings/keys"
            )
        
        # Initialize OpenAI client with OpenRouter
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/neelnanda-io/productivity_guard",
                "X-Title": "ProductivityGuard"
            }
        )
        self.debug = debug
        self.sct = mss()  # Initialize screen capture tool

        # Cache for previous screenshots to avoid duplicate processing
        self.previous_screenshots = {}
        self.last_description = ""

        # Exception list for productive activities
        self.productivity_exceptions = []

        # Input handling
        self.input_queue = queue.Queue()
        self.stop_monitoring = False
        self.in_intervention = False

        # Workday tracking
        self.workday_start_time = datetime.now()
        self.activity_log = []  # List of activity entries with timestamps
        self.last_hourly_summary = datetime.now().replace(minute=0, second=0, microsecond=0)
        self.workday_active = True
        self.activity_categories = {
            'CODING': 0, 'STUDYING': 0, 'MEETINGS': 0, 'COMMUNICATION': 0, 
            'PLANNING': 0, 'WRITING': 0, 'BREAKS': 0, 'SYSTEM': 0,
            'SOCIAL_MEDIA': 0, 'ENTERTAINMENT': 0, 'DISTRACTION': 0
        }
        self.current_activity_start = datetime.now()
        self.current_activity = None

        # Test mode settings
        self.test_mode = test_mode
        self.test_activities = []  # Predefined activities for testing
        self.test_index = 0

        # Daily logging
        self.setup_daily_logging()

        # Daily todo list
        self.daily_todos = []  # List of todo items for the day
        self.todo_counter = 1  # Counter for todo IDs
        self.setup_daily_todos()

        # Encouragement messages for different situations
        self.encouragement_messages = {
            'procrastination': [
                "💪 You've got this! Let's refocus and tackle what matters most.",
                "✨ Hey there! Time to channel that energy into something productive.",
                "🎆 Quick break's over - let's get back to crushing those goals!",
                "🚀 Ready to turn this moment around? Your future self will thank you!",
                "🎯 Focus time! What's the most important thing you could work on right now?",
                "⚡ Let's redirect that energy - you're capable of amazing things!",
                "🌱 Growth happens outside the comfort zone. Let's make progress!"
            ],
            'intervention_start': [
                "No worries, we all drift sometimes! Let's chat and get back on track.",
                "Hey, happens to the best of us! What's pulling your attention away?",
                "Time for a quick reset! What were you hoping to accomplish today?",
                "Let's pause and recalibrate - what's your next productive move?",
                "No judgment here! Let's figure out how to make the most of your time."
            ],
            'good_work': [
                "🎉 Great work! You're staying focused and making real progress.",
                "🔥 You're on fire! Keep up that productive momentum.",
                "✅ Awesome focus! You're building some serious productive habits.",
                "🏆 Fantastic! You're showing what dedicated work looks like.",
                "⭐ Stellar work! Your consistency is really paying off."
            ]
        }
        self.last_encouragement_time = datetime.now()
        
        # Pomodoro timer state
        self.pomodoro_active = False
        self.pomodoro_start_time = None
        self.pomodoro_duration = 0
        
        # Break state
        self.on_break = False
        self.break_start_time = None
        self.break_duration = 0
        self.break_activity = ""
        
        # Initialize OCR reader if available
        self.ocr_reader = None
        if OCR_AVAILABLE:
            try:
                if OCR_TYPE == "easyocr":
                    # Try GPU first, fallback to CPU if needed
                    try:
                        self.ocr_reader = easyocr.Reader(['en'], gpu=True)
                        self.debug_log("EasyOCR initialized successfully (GPU mode)")
                    except Exception as gpu_error:
                        self.debug_log(f"GPU initialization failed: {gpu_error}, falling back to CPU")
                        os.environ['CUDA_VISIBLE_DEVICES'] = ''
                        self.ocr_reader = easyocr.Reader(['en'], gpu=False)
                        self.debug_log("EasyOCR initialized successfully (CPU mode)")
                elif OCR_TYPE == "pytesseract":
                    # Test pytesseract availability
                    pytesseract.image_to_string(Image.new('RGB', (10, 10)))
                    self.debug_log("PyTesseract initialized successfully")
            except Exception as e:
                self.debug_log(f"OCR initialization failed: {e}")
                # OCR_AVAILABLE = False

        # Create debug directory for screenshots if in debug mode
        if self.debug:
            self.debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_screenshots')
            os.makedirs(self.debug_dir, exist_ok=True)
            self.debug_log(f"Debug screenshots will be saved to: {self.debug_dir}")
            self.debug_log(f"OCR available: {OCR_AVAILABLE}, Type: {OCR_TYPE}")

    def debug_log(self, message, data=None):
        """Print debug information if debug mode is enabled."""
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n[DEBUG {timestamp}] {message}")
            if data:
                if isinstance(data, str) and len(data) > 100:
                    print(f"Data: {data[:100]}... (truncated)")
                else:
                    print(f"Data: {json.dumps(data, indent=2)}")

    def get_random_encouragement(self, category='procrastination'):
        """Get a random encouragement message from the specified category."""
        import random
        messages = self.encouragement_messages.get(category, self.encouragement_messages['procrastination'])
        return random.choice(messages)

    def start_pomodoro(self, minutes):
        """Start a pomodoro timer for the specified number of minutes."""
        if self.pomodoro_active:
            print("⏰ Pomodoro timer is already running!")
            self.show_pomodoro_status()
            return
        
        self.pomodoro_active = True
        self.pomodoro_start_time = datetime.now()
        self.pomodoro_duration = minutes * 60  # Convert to seconds
        
        print(f"\n🍅 POMODORO TIMER STARTED!")
        print(f"⏰ Duration: {minutes} minutes")
        print(f"🎯 Stay focused until {(self.pomodoro_start_time + timedelta(seconds=self.pomodoro_duration)).strftime('%H:%M')}")
        print("💡 Type 'timer' to check remaining time")
        print("=" * 50)
        
        # Log the pomodoro start
        self.log_activity_to_file("PLANNING", f"Started {minutes}-minute Pomodoro session")

    def check_pomodoro_timer(self):
        """Check if pomodoro timer has finished and show alerts."""
        if not self.pomodoro_active:
            return
        
        current_time = datetime.now()
        elapsed_seconds = (current_time - self.pomodoro_start_time).total_seconds()
        
        if elapsed_seconds >= self.pomodoro_duration:
            # Timer finished!
            self.pomodoro_active = False
            minutes = self.pomodoro_duration // 60
            
            print("\n" + "=" * 60)
            print("🎉 POMODORO COMPLETE! 🎉")
            print(f"✅ You focused for {minutes} minutes - great job!")
            print("🌟 Time for a well-deserved break!")
            print("=" * 60)
            
            # Play notification sound if not disabled
            if not self.disable_sound and sys.platform == 'darwin':
                for _ in range(3):
                    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)
                    time.sleep(0.3)
            
            # Log completion
            self.log_activity_to_file("BREAKS", f"Completed {minutes}-minute Pomodoro session")
            
            # Show encouragement
            encouragement = self.get_random_encouragement('good_work')
            print(f"💬 {encouragement}\n")
            
            return True  # Return True to indicate timer completed
        
        return False  # Return False to indicate timer still running


    
    def show_pomodoro_status(self):
        """Show current pomodoro timer status."""
        if not self.pomodoro_active:
            print("⏰ No active Pomodoro timer.")
            return
        
        current_time = datetime.now()
        elapsed_seconds = (current_time - self.pomodoro_start_time).total_seconds()
        remaining_seconds = max(0, self.pomodoro_duration - elapsed_seconds)
        
        if remaining_seconds > 0:
            remaining_minutes = int(remaining_seconds // 60)
            remaining_secs = int(remaining_seconds % 60)
            total_minutes = int(self.pomodoro_duration // 60)
            elapsed_minutes = int(elapsed_seconds // 60)
            
            print(f"\n🍅 POMODORO TIMER ACTIVE")
            print(f"⏰ Time remaining: {remaining_minutes:02d}:{remaining_secs:02d}")
            print(f"📊 Progress: {elapsed_minutes}/{total_minutes} minutes")
            
            # Show simple progress bar
            progress = elapsed_seconds / self.pomodoro_duration
            bar_length = 20
            filled_length = int(bar_length * progress)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            print(f"🔥 [{bar}] {progress*100:.1f}%")
        else:
            # Timer has finished but hasn't been processed yet
            self.check_pomodoro_timer()

    def start_break(self, minutes):
        """Start a break for the specified number of minutes."""
        if self.on_break:
            print("☕ You're already on a break!")
            self.show_break_status()
            return
        
        # Get break activity from user
        print(f"\n☕ Starting a {minutes}-minute break!")
        print("What would you like to do during your break?")
        break_activity = input("Break activity: ").strip()
        
        if not break_activity:
            break_activity = "take a break"
        
        self.on_break = True
        self.break_start_time = datetime.now()
        self.break_duration = minutes * 60  # Convert to seconds
        self.break_activity = break_activity
        
        print(f"\n🛑 BREAK MODE ACTIVATED!")
        print(f"☕ Activity: {break_activity}")
        print(f"⏰ Duration: {minutes} minutes")
        print(f"🎯 Break ends at {(self.break_start_time + timedelta(seconds=self.break_duration)).strftime('%H:%M')}")
        print("📸 Screenshot monitoring is PAUSED")
        print("💡 Type 'break' to check remaining time")
        print("=" * 50)
        
        # Get AI advice for the break activity
        self.get_break_advice(break_activity, minutes)
        
        # Log the break start
        self.log_activity_to_file("BREAKS", f"Started {minutes}-minute break: {break_activity}")

    def get_break_advice(self, break_activity, duration_minutes):
        """Get AI advice for the break activity using Gemini."""
        try:
            # Load the break advice prompt
            prompt_path = os.path.join("prompts", "break_advice_prompt.md")
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r') as f:
                    prompt_template = f.read()
                
                # Format the prompt with the break activity and duration
                prompt = prompt_template.format(
                    break_activity=break_activity,
                    break_duration=duration_minutes
                )
                
                # Make API call to get advice
                response = self.call_openrouter_api(prompt, use_best_model=False)
                
                if response and response.strip():
                    print(f"\n💡 AI Break Coach says:")
                    print(f"   {response.strip()}")
                    print()
                else:
                    print(f"\n💡 Enjoy your {break_activity} break!")
                    print()
            else:
                print(f"\n💡 Enjoy your {break_activity} break!")
                print()
                
        except Exception as e:
            self.debug_log(f"Error getting break advice: {e}")
            print(f"\n💡 Enjoy your {break_activity} break!")
            print()

    def check_break_timer(self):
        """Check if break timer has finished and show alerts."""
        if not self.on_break:
            return
        
        current_time = datetime.now()
        elapsed_seconds = (current_time - self.break_start_time).total_seconds()
        
        if elapsed_seconds >= self.break_duration:
            # Break finished!
            self.on_break = False
            minutes = self.break_duration // 60
            
            print("\n" + "=" * 60)
            print("⏰ BREAK TIME IS OVER! ⏰")
            print(f"✅ You took a {minutes}-minute break: {self.break_activity}")
            print("🔋 Hope you're feeling refreshed!")
            print("📸 Screenshot monitoring is now RESUMED")
            print("=" * 60)
            
            # Play notification sound if not disabled
            if not self.disable_sound and sys.platform == 'darwin':
                for _ in range(2):
                    subprocess.run(['afplay', '/System/Library/Sounds/Ping.aiff'], check=False)
                    time.sleep(0.5)
            
            # Log completion
            self.log_activity_to_file("PLANNING", f"Break ended - resumed work after {minutes} minutes")
            
            # Reset break activity
            self.break_activity = ""
            
            return True  # Return True to indicate break completed
        
        return False  # Return False to indicate break still active

    def show_break_status(self):
        """Show current break status."""
        if not self.on_break:
            print("☕ No active break.")
            return
        
        current_time = datetime.now()
        elapsed_seconds = (current_time - self.break_start_time).total_seconds()
        remaining_seconds = max(0, self.break_duration - elapsed_seconds)
        
        if remaining_seconds > 0:
            remaining_minutes = int(remaining_seconds // 60)
            remaining_secs = int(remaining_seconds % 60)
            total_minutes = int(self.break_duration // 60)
            elapsed_minutes = int(elapsed_seconds // 60)
            
            print(f"\n☕ BREAK MODE ACTIVE")
            print(f"🎯 Activity: {self.break_activity}")
            print(f"⏰ Time remaining: {remaining_minutes:02d}:{remaining_secs:02d}")
            print(f"📊 Progress: {elapsed_minutes}/{total_minutes} minutes")
            print(f"📸 Screenshot monitoring is PAUSED")
            
            # Show simple progress bar
            progress = elapsed_seconds / self.break_duration
            bar_length = 20
            filled_length = int(bar_length * progress)
            bar = "☕" * filled_length + "░" * (bar_length - filled_length)
            print(f"🔋 [{bar}] {progress*100:.1f}%")
        else:
            # Break has finished but hasn't been processed yet
            self.check_break_timer()

    def save_debug_screenshot(self, img, monitor_index):
        """Save the last 3 screenshots for each monitor in debug mode."""
        if not self.debug:
            return

        # Create monitor-specific debug directory
        monitor_dir = os.path.join(self.debug_dir, f"monitor_{monitor_index}")
        os.makedirs(monitor_dir, exist_ok=True)

        # Get list of existing debug screenshots for this monitor
        existing_files = sorted([f for f in os.listdir(monitor_dir) if f.endswith('.png')])

        # Remove oldest files if we have more than 2 (to make room for new one)
        while len(existing_files) >= 3:
            oldest_file = os.path.join(monitor_dir, existing_files[0])
            os.remove(oldest_file)
            existing_files = existing_files[1:]

        # Save new screenshot with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_path = os.path.join(monitor_dir, f"screenshot_{timestamp}.png")

        # Save the image
        img.save(debug_path)
        self.debug_log(f"Saved debug screenshot for monitor {monitor_index}: {debug_path}")

    def process_image(self, img, max_width=800):
        """Process image to reduce size while maintaining readability."""
        # Calculate new dimensions while maintaining aspect ratio
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))

        # Resize image
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Save to bytes with compression
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG', optimize=True, quality=85)
        processed_size = len(img_buffer.getvalue())

        if self.debug:
            self.debug_log(f"Processed image size: {processed_size / 1024:.1f}KB")
            self.debug_log(f"New dimensions: {new_size[0]}x{new_size[1]}")

        return base64.b64encode(img_buffer.getvalue()).decode()

    def extract_text_from_image(self, img):
        """Extract text from a PIL Image using OCR."""
        if not OCR_AVAILABLE or not self.ocr_reader:
            return ""

        try:
            if OCR_TYPE == "easyocr":
                # Convert PIL Image to numpy array for EasyOCR
                img_array = np.array(img)
                results = self.ocr_reader.readtext(img_array)
                # Extract text from results and join with spaces
                text = ' '.join([result[1] for result in results if result[2] > 0.5])  # confidence > 0.5
                return text
            elif OCR_TYPE == "pytesseract":
                # PyTesseract works directly with PIL Images
                text = pytesseract.image_to_string(img)
                return text.strip()
        except Exception as e:
            self.debug_log(f"Error extracting text from image: {e}")
            return ""

        return ""

    def take_screenshot(self):
        """Take a screenshot of all monitors using MSS and return them as base64 encoded strings with extracted text."""

        
        print("\n📸 Taking screenshot...")
        
        self.debug_log("Taking screenshot...")
        try:
            # Get all monitors
            monitors = self.sct.monitors[1:]  # Skip the "all in one" monitor
            screenshots = []
            extracted_texts = []

            # Capture and process each monitor
            for i, monitor in enumerate(monitors, 1):
                self.debug_log(f"Capturing monitor {i}...")
                screenshot = self.sct.grab(monitor)
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)

                if self.debug:
                    self.debug_log(f"Original dimensions for monitor {i}: {img.width}x{img.height}")
                    self.debug_log(f"Original size for monitor {i}: {len(screenshot.rgb) / 1024:.1f}KB")
                    self.save_debug_screenshot(img, i)

                # Extract text from the image before processing
                extracted_text = self.extract_text_from_image(img)
                extracted_texts.append(extracted_text)

                if self.debug and extracted_text:
                    self.debug_log(f"Extracted text from monitor {i} (first 200 chars): {extracted_text[:200]}")

                # Process and encode the image
                encoded_image = self.process_image(img)
                screenshots.append(encoded_image)

            self.debug_log("Screenshots captured successfully")
    
            return screenshots, extracted_texts
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None, None

    def _check_with_model(self, screenshots, extracted_texts, model_name, use_reasoning=False, print_reasoning=False):
        """Send screenshots to specified model and check if user is procrastinating."""
        if not screenshots:
            self.debug_log("No screenshots available to check")
            return False, ""

        try:
            # Check if screenshots are identical to previous ones for this model
            current_hashes = []
            for screenshot in screenshots:
                current_hash = hashlib.md5(screenshot.encode()).hexdigest()
                current_hashes.append(current_hash)

            cache_key = (tuple(current_hashes), model_name)
            if cache_key in self.previous_screenshots:
                self.debug_log(f"Screenshots identical to previous check with {model_name}, reusing last result")
                result, cached_response = self.previous_screenshots[cache_key]
                print(f"Decision (from cache, {model_name}): {'Procrastinating' if result else 'Working'}")
                return result, cached_response

            self.debug_log(f"Sending screenshots to {model_name} for analysis...")

            # Add exceptions if any exist
            if self.productivity_exceptions:
                exceptions_text = "\n\nThe following things are productive. Previously, you've accidentally mistaken these for unproductive things, so if what the user is doing is plausibly this, please don't interrupt:\n" + "\n".join(self.productivity_exceptions)
                prompt_text = SYSTEM_PROMPT + exceptions_text
            else:
                prompt_text = SYSTEM_PROMPT

            # Add extracted text if available
            if OCR_AVAILABLE and extracted_texts:
                text_content = []
                for i, text in enumerate(extracted_texts, 1):
                    if text.strip():
                        text_content.append(f"Monitor {i} text content: {text}")

                if text_content:
                    prompt_text += "\n\nExtracted text from screens:\n" + "\n\n".join(text_content)

            prompt_text += "\n\nFirst, describe what you see in 1-2 sentences.\nThen on a new line, end your response with ONLY with the word 'yes' or 'no' (no punctuation) and nothing else."

            # Create message content with all screenshots
            content: List[Dict[str, Any]] = [{
                "type": "text", 
                "text": prompt_text
            }]

            # Add each screenshot as a separate image
            for i, screenshot in enumerate(screenshots, 1):
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot
                    }
                })

            messages = [{
                "role": "user",
                "content": content
            }]

            if self.debug:
                # Create a debug version of the message without the actual image data
                debug_content = [{"type": "text", "text": "Analyze these screenshots and determine if the person is procrastinating..."}]
                for i in range(len(screenshots)):
                    debug_content.append({
                        "type": "image",
                        "source": "[IMAGE DATA]"
                    })
                debug_messages = [{"role": "user", "content": debug_content}]
                self.debug_log("Sending message to Gemini:", debug_messages)

            # Convert message format for OpenAI API
            openai_messages = []
            
            # Add system message
            openai_messages.append({
                "role": "system",
                "content": SYSTEM_PROMPT
            })
            
            # Convert content format for OpenAI
            openai_content = []
            for item in content:
                if item["type"] == "text":
                    openai_content.append({
                        "type": "text",
                        "text": item["text"]
                    })
                elif item["type"] == "image":
                    # OpenAI expects image_url format
                    openai_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{item['source']['media_type']};base64,{item['source']['data']}"
                        }
                    })
            
            openai_messages.append({
                "role": "user",
                "content": openai_content
            })
            
            # Show loading feedback
            if not self.in_intervention:  # Only show if not in intervention mode
                print("🔍 Analyzing screenshots... ", end='', flush=True)
            
            # Make the API call
            extra_body = {}
            if use_reasoning and ("pro" in model_name.lower() or "reasoning" in model_name.lower() or "thinking" in model_name.lower()):
                extra_body["reasoning"] = {}
            
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages,
                extra_body=extra_body
            )
            
            # Clear loading message
            if not self.in_intervention:
                print("\r" + " " * 30 + "\r", end='', flush=True)
            


            response = completion.choices[0].message.content.strip()
            self.debug_log(f"Full response from {model_name}: {response}")

            # Print reasoning if requested (for Flash model)
            if print_reasoning:
                print(f"\nFlash reasoning about potential procrastination: {response}")

            # Store the description (everything except the last line)
            self.last_description = '\n'.join(response.split('\n')[:-1])

            # Extract the yes/no answer by looking at the last line and removing punctuation
            last_line = response.split('\n')[-1].strip().lower()
            last_line = ''.join(c for c in last_line if c.isalpha())  # Remove all non-letter characters
            is_procrastinating = last_line == 'yes'

            # Print the decision with better formatting, considering pomodoro state
            status_icon = "⚠️" if is_procrastinating else "✅"
            status_text = "Procrastinating" if is_procrastinating else "Working"
            
            if self.pomodoro_active:
                # During pomodoro, show decision more subtly to avoid disrupting timer
                print(f" {status_icon}", end='', flush=True)
            else:
                print(f"\n{status_icon} Decision ({model_name}): {status_text}")

            # Cache the result with full response
            self.previous_screenshots[cache_key] = (is_procrastinating, response)

            if self.debug:
                self.debug_log(f"Extracted answer: {last_line}")
                self.debug_log(f"Procrastination detected: {is_procrastinating}")

            return is_procrastinating, response
        except Exception as e:
            print(f"Error checking procrastination with {model_name}: {e}")
            return False, ""

    def check_procrastination(self, screenshots, extracted_texts=None):
        """Two-step procrastination check: Flash first, then Pro with reasoning if needed."""
        if not screenshots:
            self.debug_log("No screenshots available to check")
            return False

        # Check if budget mode is enabled
        budget_mode = os.getenv('BUDGET_MODE', 'false').lower() == 'true'
        
        # Step 1: Quick check with Flash (always print reasoning)
        flash_model = os.getenv('MEDIUM_MODEL', 'google/gemini-2.5-flash')
        self.debug_log("Step 1: Checking with Flash model...")
        
        flash_result, flash_response = self._check_with_model(
            screenshots, extracted_texts, flash_model, 
            use_reasoning=False, print_reasoning=True
        )
        
        if not flash_result:
            # Flash says not procrastinating, we're done
            self.debug_log("Flash says not procrastinating, skipping Pro check")
            return False
        
        # If budget mode is enabled, skip Pro model and use Flash result
        if budget_mode:
            self.debug_log("Budget mode enabled - using Flash result only")
            if not self.pomodoro_active:
                print(f"\n💡 Flash (Budget mode) response: {flash_response}")
            return flash_result
        
        # Step 2: Flash detected procrastination, verify with Pro + reasoning
        pro_model = os.getenv('BEST_MODEL', 'google/gemini-2.5-pro')
        self.debug_log("Step 2: Flash detected procrastination, verifying with Pro + reasoning...")
        
        pro_result, pro_response = self._check_with_model(
            screenshots, extracted_texts, pro_model, 
            use_reasoning=True, print_reasoning=False
        )
        
        # Always print Pro's response, but consider pomodoro state
        if not self.pomodoro_active:
            print(f"\n🤖 Pro (Gemini 2.5) response: {pro_response}")
        else:
            # During pomodoro, just show a simple indicator that analysis completed
            print("🤖", end='', flush=True)
        
        if pro_result:
            self.debug_log("Both Flash and Pro agree: procrastination detected!")
        else:
            self.debug_log("Pro disagrees with Flash: not procrastinating")
            
        return pro_result

    def simulate_activity_categorization(self):
        """Simulate activity categorization for testing purposes."""
        if not self.test_activities:
            # Default test activities that simulate a workday
            self.test_activities = [
                ('CODING', 'Working on Python script'),
                ('CODING', 'Debugging application'),
                ('SOCIAL_MEDIA', 'Checking Twitter'),
                ('CODING', 'Writing unit tests'),
                ('BREAKS', 'Coffee break'),
                ('STUDYING', 'Reading documentation'),
                ('ENTERTAINMENT', 'Watching YouTube'),
                ('CODING', 'Code review'),
                ('MEETINGS', 'Team standup'),
                ('DISTRACTION', 'Random browsing'),
                ('CODING', 'Implementing feature'),
                ('WRITING', 'Writing documentation'),
            ]

        if self.test_index < len(self.test_activities):
            activity = self.test_activities[self.test_index]
            self.test_index += 1
            return activity[0], activity[1]
        else:
            # Cycle through activities
            self.test_index = 0
            activity = self.test_activities[self.test_index]
            self.test_index += 1
            return activity[0], activity[1]

    def categorize_activity(self, screenshots, extracted_texts=None):
        """Categorize the current activity instead of just checking procrastination."""
        if not screenshots:
            self.debug_log("No screenshots available to categorize")
            return None, ""

        try:
            # Use the activity categorization prompt
            prompt_text = activity_categorization_prompt

            # Add exceptions if any exist
            if self.productivity_exceptions:
                exceptions_text = "\n\nNOTE: The following activities are confirmed as productive for this user:\n" + "\n".join(self.productivity_exceptions)
                prompt_text += exceptions_text

            # Add extracted text if available
            if OCR_AVAILABLE and extracted_texts:
                text_content = []
                for i, text in enumerate(extracted_texts, 1):
                    if text.strip():
                        text_content.append(f"Monitor {i} text content: {text}")

                if text_content:
                    prompt_text += "\n\nExtracted text from screens:\n" + "\n\n".join(text_content)

            # Create message content with all screenshots
            content: List[Dict[str, Any]] = [{
                "type": "text", 
                "text": prompt_text
            }]

            # Add each screenshot as a separate image
            for i, screenshot in enumerate(screenshots, 1):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screenshot}"
                    }
                })

            openai_messages = [
                {
                    "role": "system",
                    "content": activity_categorization_prompt
                },
                {
                    "role": "user",
                    "content": content
                }
            ]

            # Show loading feedback
            if not self.in_intervention:
                print("🔍 Categorizing activity... ", end='', flush=True)

            # Make the API call
            model_name = os.getenv('MEDIUM_MODEL', 'google/gemini-2.5-flash')
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=openai_messages
            )

            # Clear loading message
            if not self.in_intervention:
                print("\r" + " " * 30 + "\r", end='', flush=True)
            


            response = completion.choices[0].message.content.strip()
            self.debug_log(f"Activity categorization response: {response}")

            # Extract category from response
            category = None
            for line in response.split('\n'):
                if line.strip().startswith('CATEGORY:'):
                    category = line.split('CATEGORY:')[1].strip().upper()
                    break

            return category, response

        except Exception as e:
            self.debug_log(f"Error categorizing activity: {e}")
            return None, ""

    def log_activity(self, category, description=""):
        """Log an activity with timestamp and update time tracking."""
        if not self.workday_active:
            return

        current_time = datetime.now()
        
        # If we have a previous activity, calculate its duration and add to totals
        if self.current_activity and self.current_activity_start:
            duration = (current_time - self.current_activity_start).total_seconds()
            if self.current_activity in self.activity_categories:
                self.activity_categories[self.current_activity] += duration

        # Log the activity
        activity_entry = {
            'timestamp': current_time,
            'category': category,
            'description': description,
            'duration_start': current_time
        }
        self.activity_log.append(activity_entry)

        # Update current activity tracking
        self.current_activity = category
        self.current_activity_start = current_time

        # Log to file as well
        self.log_activity_to_file(category, description)

        self.debug_log(f"Logged activity: {category} - {description}")

    def check_hourly_summary(self):
        """Check if it's time for an hourly summary and generate one if needed."""
        current_time = datetime.now()
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)
        
        if current_hour > self.last_hourly_summary:
            self.generate_hourly_summary()
            self.last_hourly_summary = current_hour

    def generate_hourly_summary(self):
        """Generate and display an hourly productivity summary."""
        if not self.workday_active:
            return

        current_time = datetime.now()
        hours_worked = (current_time - self.workday_start_time).total_seconds() / 3600

        print(f"\n⏰ HOURLY UPDATE - {current_time.strftime('%H:%M')}")
        print(f"📅 Workday duration: {hours_worked:.1f} hours")
        
        # Calculate total productive vs unproductive time
        productive_categories = ['CODING', 'STUDYING', 'MEETINGS', 'COMMUNICATION', 'PLANNING', 'WRITING']
        neutral_categories = ['BREAKS', 'SYSTEM']
        unproductive_categories = ['SOCIAL_MEDIA', 'ENTERTAINMENT', 'DISTRACTION']

        productive_time = sum(self.activity_categories[cat] for cat in productive_categories)
        neutral_time = sum(self.activity_categories[cat] for cat in neutral_categories)
        unproductive_time = sum(self.activity_categories[cat] for cat in unproductive_categories)
        total_time = productive_time + neutral_time + unproductive_time

        if total_time > 0:
            productive_pct = (productive_time / total_time) * 100
            print(f"🎯 Productivity: {productive_pct:.1f}% productive, {(neutral_time/total_time)*100:.1f}% neutral, {(unproductive_time/total_time)*100:.1f}% unproductive")

        # Show top activities
        top_activities = sorted(self.activity_categories.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_activities[0][1] > 0:
            print("📊 Top activities:")
            for category, seconds in top_activities:
                if seconds > 0:
                    minutes = seconds / 60
                    print(f"   • {category.title()}: {minutes:.0f} minutes")

        # Show todo progress
        if self.daily_todos:
            completed = sum(1 for todo in self.daily_todos if todo["completed"])
            total = len(self.daily_todos)
            progress = (completed / total) * 100 if total > 0 else 0
            print(f"📝 Todo progress: {completed}/{total} ({progress:.0f}%)")

        print()

        # Also save to file
        self.save_hourly_summary_to_file()

    def generate_workday_summary(self):
        """Generate a comprehensive end-of-workday summary with AI analysis."""
        if not self.workday_active:
            return

        # Finalize current activity
        if self.current_activity and self.current_activity_start:
            duration = (datetime.now() - self.current_activity_start).total_seconds()
            if self.current_activity in self.activity_categories:
                self.activity_categories[self.current_activity] += duration

        current_time = datetime.now()
        total_workday_duration = current_time - self.workday_start_time
        total_seconds = total_workday_duration.total_seconds()

        print(f"\n🎯 WORKDAY COMPLETE - {current_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"⏱️  Duration: {total_workday_duration}")

        # Prepare data for AI summary
        time_breakdown = {}
        for category, seconds in self.activity_categories.items():
            if seconds > 0:
                hours = seconds / 3600
                minutes = (seconds % 3600) / 60
                percentage = (seconds / total_seconds) * 100 if total_seconds > 0 else 0
                time_breakdown[category] = {
                    'hours': hours,
                    'minutes': minutes,
                    'total_minutes': seconds / 60,
                    'percentage': percentage
                }

        # Generate AI summary
        try:
            summary_data = {
                'workday_date': current_time.strftime('%Y-%m-%d'),
                'start_time': self.workday_start_time.strftime('%H:%M'),
                'end_time': current_time.strftime('%H:%M'),
                'total_duration': str(total_workday_duration),
                'time_breakdown': time_breakdown,
                'activity_log_summary': self._get_activity_log_summary()
            }

            ai_summary = self._generate_ai_summary(summary_data)
            print(ai_summary)

        except Exception as e:
            self.debug_log(f"Error generating AI summary: {e}")
            # Fallback to basic summary
            self._generate_basic_summary(time_breakdown, total_workday_duration)

    def _get_activity_log_summary(self):
        """Get a condensed summary of the activity log for AI analysis."""
        if not self.activity_log:
            return "No activities logged."

        summary_entries = []
        for entry in self.activity_log[-10:]:  # Last 10 activities
            time_str = entry['timestamp'].strftime('%H:%M')
            summary_entries.append(f"{time_str}: {entry['category']} - {entry.get('description', '')}")
        
        return "\n".join(summary_entries)

    def _generate_ai_summary(self, summary_data):
        """Generate AI-powered workday summary and advice."""
        # Format the data for the AI prompt
        time_breakdown_text = []
        for category, data in summary_data['time_breakdown'].items():
            hours = int(data['hours'])
            minutes = int(data['minutes'])
            time_breakdown_text.append(
                f"- **{category.title()}:** {hours} hours {minutes} minutes - {data['percentage']:.1f}%"
            )

        prompt = f"""
{workday_summary_prompt}

WORKDAY DATA:
Date: {summary_data['workday_date']}
Duration: {summary_data['start_time']} - {summary_data['end_time']} ({summary_data['total_duration']})

Time Breakdown:
{chr(10).join(time_breakdown_text)}

Recent Activity Log:
{summary_data['activity_log_summary']}
"""

        try:
            # Use Flash model if budget mode is enabled
            budget_mode = os.getenv('BUDGET_MODE', 'false').lower() == 'true'
            if budget_mode:
                model_name = os.getenv('MEDIUM_MODEL', 'google/gemini-2.5-flash')
            else:
                model_name = os.getenv('BEST_MODEL', 'google/gemini-2.5-pro')
            
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a productivity coach. Analyze the workday data and provide a structured summary with actionable advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            return completion.choices[0].message.content.strip()

        except Exception as e:
            self.debug_log(f"Error generating AI summary: {e}")
            return "Error generating AI summary. See basic summary above."

    def _generate_basic_summary(self, time_breakdown, total_duration):
        """Generate a basic fallback summary without AI."""
        print("\n📊 WORKDAY SUMMARY")
        print(f"⏱️  Total time: {total_duration}")
        
        if time_breakdown:
            print("\n🕐 Time breakdown:")
            for category, data in sorted(time_breakdown.items(), key=lambda x: x[1]['total_minutes'], reverse=True):
                hours = int(data['hours'])
                minutes = int(data['minutes'])
                print(f"   • {category.title()}: {hours}h {minutes}m ({data['percentage']:.1f}%)")

    def end_workday(self):
        """End the current workday and generate summary."""
        if not self.workday_active:
            print("Workday is not currently active.")
            return

        print("\n🎯 Ending workday...")
        self.workday_active = False
        self.generate_workday_summary()
        
        # Ask for todos for next session
        self.collect_next_session_todos()
        
        # Stop monitoring
        self.stop_monitoring = True
        
        # Save final summary to file
        self.save_workday_summary_to_file()
        
        print("\nProductivityGuard stopped. Have a great rest of your day! 🌟")

    def setup_daily_logging(self):
        """Set up daily logging files and folders."""
        # Create data directories if they don't exist
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.logs_dir = os.path.join(self.data_dir, 'logs')
        self.summaries_dir = os.path.join(self.data_dir, 'summaries')
        
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.summaries_dir, exist_ok=True)
        
        # Set up daily log file
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_log_file = os.path.join(self.logs_dir, f'{today}_activity_log.md')
        self.daily_summary_file = os.path.join(self.summaries_dir, f'{today}_workday_summary.md')
        
        # Initialize daily log if it doesn't exist
        if not os.path.exists(self.daily_log_file):
            self.initialize_daily_log()
        else:
            # If log exists, we're resuming - log the resume
            self.append_to_daily_log(f"\n## 🔄 Session Resumed - {datetime.now().strftime('%H:%M:%S')}\n")

    def initialize_daily_log(self):
        """Create the initial daily activity log file."""
        today = datetime.now().strftime('%Y-%m-%d')
        start_time = self.workday_start_time.strftime('%H:%M:%S')
        
        initial_content = f"""# 📅 Daily Activity Log - {today}

**Workday Started:** {start_time}
**Goal:** Track activities and maintain productivity throughout the day

## 🎯 Today's Focus Areas
<!-- Add your main goals for the day here -->

## 📊 Activity Timeline

### Session Started - {start_time}
"""
        
        with open(self.daily_log_file, 'w', encoding='utf-8') as f:
            f.write(initial_content)
        
        self.debug_log(f"Daily log initialized: {self.daily_log_file}")

    def append_to_daily_log(self, content):
        """Append content to the daily log file."""
        try:
            with open(self.daily_log_file, 'a', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self.debug_log(f"Error writing to daily log: {e}")

    def log_activity_to_file(self, category, description=""):
        """Log an activity to the daily log file."""
        timestamp = datetime.now().strftime('%H:%M')
        
        # Create activity entry
        activity_entry = f"- **{timestamp}** - {category.title()}"
        if description:
            activity_entry += f": {description}"
        activity_entry += "\n"
        
        self.append_to_daily_log(activity_entry)

    def save_hourly_summary_to_file(self):
        """Save hourly summary to the daily log file."""
        current_time = datetime.now()
        hours_worked = (current_time - self.workday_start_time).total_seconds() / 3600
        
        # Calculate productivity stats
        productive_categories = ['CODING', 'STUDYING', 'MEETINGS', 'COMMUNICATION', 'PLANNING', 'WRITING']
        neutral_categories = ['BREAKS', 'SYSTEM']
        unproductive_categories = ['SOCIAL_MEDIA', 'ENTERTAINMENT', 'DISTRACTION']

        productive_time = sum(self.activity_categories[cat] for cat in productive_categories)
        neutral_time = sum(self.activity_categories[cat] for cat in neutral_categories)
        unproductive_time = sum(self.activity_categories[cat] for cat in unproductive_categories)
        total_time = productive_time + neutral_time + unproductive_time

        summary_content = f"""
### ⏰ Hourly Update - {current_time.strftime('%H:%M')}
- **Duration**: {hours_worked:.1f} hours
"""
        
        if total_time > 0:
            productive_pct = (productive_time / total_time) * 100
            summary_content += f"- **Productivity**: {productive_pct:.1f}% productive, {(neutral_time/total_time)*100:.1f}% neutral, {(unproductive_time/total_time)*100:.1f}% unproductive\n"

        # Show top activities
        top_activities = sorted(self.activity_categories.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_activities[0][1] > 0:
            summary_content += "- **Top Activities**:\n"
            for category, seconds in top_activities:
                if seconds > 0:
                    minutes = seconds / 60
                    summary_content += f"  - {category.title()}: {minutes:.0f} minutes\n"

        # Add todo progress to hourly summary
        if self.daily_todos:
            completed = sum(1 for todo in self.daily_todos if todo["completed"])
            total = len(self.daily_todos)
            progress = (completed / total) * 100 if total > 0 else 0
            summary_content += f"- **Todo Progress**: {completed}/{total} ({progress:.0f}%)\n"

        summary_content += "\n"
        self.append_to_daily_log(summary_content)

    def save_workday_summary_to_file(self):
        """Save the complete workday summary to a separate file."""
        # Remove workday_active check - we should be able to save summary even after workday ends

        # Generate the summary data first
        current_time = datetime.now()
        total_workday_duration = current_time - self.workday_start_time
        total_seconds = total_workday_duration.total_seconds()

        # Finalize current activity
        if self.current_activity and self.current_activity_start:
            duration = (current_time - self.current_activity_start).total_seconds()
            if self.current_activity in self.activity_categories:
                self.activity_categories[self.current_activity] += duration

        # Prepare time breakdown
        time_breakdown = {}
        for category, seconds in self.activity_categories.items():
            if seconds > 0:
                hours = seconds / 3600
                minutes = (seconds % 3600) / 60
                percentage = (seconds / total_seconds) * 100 if total_seconds > 0 else 0
                time_breakdown[category] = {
                    'hours': hours,
                    'minutes': minutes,
                    'total_minutes': seconds / 60,
                    'percentage': percentage
                }

        # Create summary content
        today = current_time.strftime('%Y-%m-%d')
        summary_content = f"""# 🎯 Workday Summary - {today}

**Date:** {current_time.strftime('%Y-%m-%d')}
**Duration:** {self.workday_start_time.strftime('%H:%M')} - {current_time.strftime('%H:%M')} ({total_workday_duration})
**Total Time:** {total_workday_duration}

## 📊 Time Breakdown

"""

        # Add time breakdown
        if time_breakdown:
            for category, data in sorted(time_breakdown.items(), key=lambda x: x[1]['total_minutes'], reverse=True):
                hours = int(data['hours'])
                minutes = int(data['minutes'])
                summary_content += f"- **{category.title()}:** {hours}h {minutes}m ({data['percentage']:.1f}%)\n"

        # Calculate productivity metrics
        productive_categories = ['CODING', 'STUDYING', 'MEETINGS', 'COMMUNICATION', 'PLANNING', 'WRITING']
        neutral_categories = ['BREAKS', 'SYSTEM']
        unproductive_categories = ['SOCIAL_MEDIA', 'ENTERTAINMENT', 'DISTRACTION']

        productive_time = sum(self.activity_categories.get(cat, 0) for cat in productive_categories)
        neutral_time = sum(self.activity_categories.get(cat, 0) for cat in neutral_categories)
        unproductive_time = sum(self.activity_categories.get(cat, 0) for cat in unproductive_categories)
        total_tracked_time = productive_time + neutral_time + unproductive_time

        productivity_score = 5  # Default score
        if total_tracked_time > 0:
            productive_pct = (productive_time / total_tracked_time) * 100
            productivity_score = min(10, max(1, (productive_pct / 10)))  # Simple scoring
            
            summary_content += f"""
## 🎯 Productivity Metrics

- **Overall Productivity:** {productive_pct:.1f}%
- **Productivity Score:** {productivity_score:.1f}/10
- **Productive Time:** {productive_time/3600:.1f} hours
- **Neutral Time:** {neutral_time/3600:.1f} hours  
- **Unproductive Time:** {unproductive_time/3600:.1f} hours

"""

        # Add todo summary
        if self.daily_todos:
            completed_todos = [t for t in self.daily_todos if t["completed"]]
            pending_todos = [t for t in self.daily_todos if not t["completed"]]
            
            summary_content += f"""## 📝 Todo Summary

**Completed ({len(completed_todos)}):**
"""
            for todo in completed_todos:
                summary_content += f"- ✅ {todo['text']}\n"
            
            if pending_todos:
                summary_content += f"\n**Remaining ({len(pending_todos)}):**\n"
                for todo in pending_todos:
                    summary_content += f"- ⬜ {todo['text']}\n"
            
            total_todos = len(self.daily_todos)
            progress = (len(completed_todos) / total_todos) * 100 if total_todos > 0 else 0
            summary_content += f"\n**Progress**: {len(completed_todos)}/{total_todos} ({progress:.0f}%)\n\n"

        # Add activity log summary
        summary_content += f"""## 📊 Activity Summary

Recent activities from today's log:
"""
        
        # Add last 10 activities
        for entry in self.activity_log[-10:]:
            time_str = entry['timestamp'].strftime('%H:%M')
            summary_content += f"- **{time_str}** - {entry['category'].title()}"
            if entry.get('description'):
                summary_content += f": {entry['description']}"
            summary_content += "\n"

        # Try to get AI-generated insights
        try:
            ai_insights = self._generate_ai_summary({
                'workday_date': today,
                'start_time': self.workday_start_time.strftime('%H:%M'),
                'end_time': current_time.strftime('%H:%M'),
                'total_duration': str(total_workday_duration),
                'time_breakdown': time_breakdown,
                'activity_log_summary': self._get_activity_log_summary()
            })
            summary_content += f"""
## 🤖 AI Analysis & Recommendations

{ai_insights}
"""
        except Exception as e:
            self.debug_log(f"Could not generate AI insights: {e}")
            summary_content += f"""
## 💡 Key Insights

- Workday completed successfully
- Total productive time: {productive_time/3600:.1f} hours
- Consider reviewing the time breakdown above for improvement opportunities

"""

        summary_content += f"""
---
*Generated by ProductivityGuard on {current_time.strftime('%Y-%m-%d at %H:%M')}*
"""

        # Write to summary file
        try:
            with open(self.daily_summary_file, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            
            print(f"\n📄 Workday summary saved to: {self.daily_summary_file}")
            
            # Also append summary to daily log
            self.append_to_daily_log(f"""
## 🎯 End of Day Summary - {current_time.strftime('%H:%M')}

**Final Duration:** {total_workday_duration}
**Productivity Score:** {productivity_score:.1f}/10

Full summary saved to: `{os.path.basename(self.daily_summary_file)}`

---
""")
            
        except Exception as e:
            self.debug_log(f"Error saving workday summary: {e}")

    def setup_daily_todos(self):
        """Set up daily todo list file and load existing todos if any."""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_todo_file = os.path.join(self.data_dir, f'{today}_daily_todos.json')
        
        # Initialize empty todo list
        self.daily_todos = []
        self.todo_counter = 1
        
        # Load existing todos if file exists
        if os.path.exists(self.daily_todo_file):
            try:
                with open(self.daily_todo_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.daily_todos = data.get('todos', [])
                    self.todo_counter = data.get('next_id', 1)
                self.debug_log(f"Loaded {len(self.daily_todos)} existing todos")
                
                # Load next session todos if any (for continuing same day)
                next_session_todos = self.load_next_session_todos()
                if next_session_todos:
                    self.save_todos()  # Save updated todos with next session items
                    
            except Exception as e:
                self.debug_log(f"Error loading todos: {e}")
                self.daily_todos = []
                self.todo_counter = 1
        else:
            # New day - offer to import previous day todos first
            self.offer_previous_day_import()
            
            # Load next session todos if any
            next_session_todos = self.load_next_session_todos()
            
            # Ask user for additional todos
            self.collect_daily_todos()
            
            # Save all todos after collection
            if self.daily_todos or next_session_todos:
                self.save_todos()

    def collect_daily_todos(self):
        """Collect daily todos from user at program start."""
        if self.test_mode:
            # Use predefined todos for testing
            self.daily_todos = [
                {"id": 1, "text": "Complete feature implementation", "completed": False, "created_at": datetime.now().isoformat()},
                {"id": 2, "text": "Review pull requests", "completed": False, "created_at": datetime.now().isoformat()},
                {"id": 3, "text": "Update documentation", "completed": False, "created_at": datetime.now().isoformat()}
            ]
            self.todo_counter = 4
            self.save_todos()
            return

        print("\n" + "="*60)
        print("📝 DAILY TODO LIST SETUP")
        print("="*60)
        print("What do you want to get done today?")
        print("Enter your todo items one by one. Press Enter with empty input when done.")
        print("-" * 60)

        todo_items = []
        while True:
            try:
                item = input(f"Todo #{len(todo_items) + 1}: ").strip()
                if not item:
                    break
                todo_items.append(item)
                print(f"✅ Added: {item}")
            except (EOFError, KeyboardInterrupt):
                break

        # Convert to todo objects
        for item in todo_items:
            todo = {
                "id": self.todo_counter,
                "text": item,
                "completed": False,
                "created_at": datetime.now().isoformat()
            }
            self.daily_todos.append(todo)
            self.todo_counter += 1

        if self.daily_todos:
            print(f"\n✅ Created {len(self.daily_todos)} todos for today!")
            self.save_todos()
            self.log_todos_to_activity_file()
        else:
            print("\n📝 No todos created. You can add them later during the day.")

        print("=" * 60)

    def save_todos(self):
        """Save todos to JSON file."""
        try:
            data = {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "todos": self.daily_todos,
                "next_id": self.todo_counter
            }
            with open(self.daily_todo_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.debug_log(f"Error saving todos: {e}")

    def log_todos_to_activity_file(self):
        """Log current todos to the daily activity log."""
        if not self.daily_todos:
            return
            
        todo_content = "\n## 📝 Daily Todo List\n\n"
        for todo in self.daily_todos:
            status = "✅" if todo["completed"] else "⬜"
            todo_content += f"- {status} {todo['text']}\n"
        todo_content += "\n"
        
        self.append_to_daily_log(todo_content)

    def show_todos(self):
        """Display current todo list."""
        if not self.daily_todos:
            print("\n📝 No todos for today.")
            return

        print("\n📝 TODAY'S TODOS:")
        print("-" * 40)
        for todo in self.daily_todos:
            status = "✅" if todo["completed"] else "⬜"
            print(f"{status} {todo['id']}. {todo['text']}")
        
        completed = sum(1 for todo in self.daily_todos if todo["completed"])
        total = len(self.daily_todos)
        if total > 0:
            progress = (completed / total) * 100
            print(f"\n📊 Progress: {completed}/{total} ({progress:.0f}%)")

    def complete_todo(self, todo_id):
        """Mark a todo as completed."""
        for todo in self.daily_todos:
            if todo["id"] == todo_id:
                if not todo["completed"]:
                    todo["completed"] = True
                    todo["completed_at"] = datetime.now().isoformat()
                    print(f"✅ Completed: {todo['text']}")
                    self.save_todos()
                    self.log_activity_to_file("PLANNING", f"Completed todo: {todo['text']}")
                    return True
                else:
                    print(f"ℹ️  Todo #{todo_id} is already completed.")
                    return False
        print(f"❌ Todo #{todo_id} not found.")
        return False

    def add_todo(self, text):
        """Add a new todo item."""
        todo = {
            "id": self.todo_counter,
            "text": text,
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        self.daily_todos.append(todo)
        self.todo_counter += 1
        print(f"✅ Added todo #{todo['id']}: {text}")
        self.save_todos()
        self.log_activity_to_file("PLANNING", f"Added todo: {text}")

    def suggest_todo_updates(self, activity_description):
        """Use AI to suggest todo updates based on current activity."""
        if not self.daily_todos or not activity_description:
            return

        try:
            # Create a prompt for todo suggestions
            todo_list = "\n".join([f"- {'✅' if t['completed'] else '⬜'} {t['text']}" for t in self.daily_todos])
            
            prompt = f"""
Based on the user's current activity and their todo list, suggest if any todos should be marked as completed or if new todos should be added.

Current Activity: {activity_description}

Current Todo List:
{todo_list}

Respond in this format:
COMPLETE: [todo text] (if any todo should be marked complete)
ADD: [new todo text] (if a new todo should be added)
NONE: (if no changes needed)

Only suggest obvious completions or important additions. Be conservative.
"""

            model_name = os.getenv('MEDIUM_MODEL', 'google/gemini-2.5-flash')
            completion = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a productivity assistant that helps manage todo lists."},
                    {"role": "user", "content": prompt}
                ]
            )

            suggestion = completion.choices[0].message.content.strip()
            
            if suggestion.startswith("COMPLETE:"):
                todo_text = suggestion[9:].strip()
                # Find matching todo and suggest completion
                for todo in self.daily_todos:
                    if not todo["completed"] and todo_text.lower() in todo["text"].lower():
                        print(f"\n🤖 AI Suggestion: Complete todo '{todo['text']}'? (Type 'done {todo['id']}' to confirm)")
                        break
            elif suggestion.startswith("ADD:"):
                new_todo = suggestion[4:].strip()
                print(f"\n🤖 AI Suggestion: Add todo '{new_todo}'? (Type 'add {new_todo}' to confirm)")

        except Exception as e:
            self.debug_log(f"Error generating todo suggestions: {e}")

    def collect_next_session_todos(self):
        """Collect todos for the next session when ending workday."""
        if self.test_mode:
            return  # Skip in test mode
            
        print("\n" + "="*60)
        print("📝 NEXT SESSION TODOS")
        print("="*60)
        print("Is there anything you'd like to add to your todos for the next session?")
        print("(These will be available when you start ProductivityGuard again)")
        print("Enter todo items one by one. Press Enter with empty input when done.")
        print("-" * 60)
        
        next_session_todos = []
        while True:
            try:
                item = input(f"Next session todo #{len(next_session_todos) + 1}: ").strip()
                if not item:
                    break
                next_session_todos.append(item)
                print(f"✅ Added: {item}")
            except (EOFError, KeyboardInterrupt):
                break
        
        if next_session_todos:
            self.save_next_session_todos(next_session_todos)
            print(f"\n✅ Saved {len(next_session_todos)} todos for next session!")
        else:
            print("\n📝 No next session todos added.")
        
        print("=" * 60)

    def save_next_session_todos(self, todos):
        """Save next session todos to a file."""
        try:
            next_session_file = os.path.join(self.data_dir, 'next_session_todos.json')
            data = {
                "created_at": datetime.now().isoformat(),
                "todos": todos
            }
            with open(next_session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.debug_log(f"Saved {len(todos)} next session todos")
        except Exception as e:
            self.debug_log(f"Error saving next session todos: {e}")

    def load_next_session_todos(self):
        """Load and integrate next session todos if they exist."""
        next_session_file = os.path.join(self.data_dir, 'next_session_todos.json')
        
        if not os.path.exists(next_session_file):
            return []
            
        try:
            with open(next_session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                todos = data.get('todos', [])
                
            if todos:
                print(f"\n📥 Found {len(todos)} todos from previous session:")
                for i, todo in enumerate(todos, 1):
                    print(f"  {i}. {todo}")
                
                # Add them to current todos
                for todo_text in todos:
                    todo = {
                        "id": self.todo_counter,
                        "text": todo_text,
                        "completed": False,
                        "created_at": datetime.now().isoformat(),
                        "from_previous_session": True
                    }
                    self.daily_todos.append(todo)
                    self.todo_counter += 1
                
                # Remove the next session file after loading
                os.remove(next_session_file)
                print(f"✅ Added {len(todos)} todos from previous session!")
                
                return todos
        except Exception as e:
            self.debug_log(f"Error loading next session todos: {e}")
            
        return []

    def get_previous_day_todos(self):
        """Get undone todos from the previous day."""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            yesterday_file = os.path.join(self.data_dir, f'{yesterday}_daily_todos.json')
            
            if not os.path.exists(yesterday_file):
                return []
                
            with open(yesterday_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                todos = data.get('todos', [])
                
            # Filter for uncompleted todos
            undone_todos = [todo for todo in todos if not todo.get('completed', False)]
            return undone_todos
            
        except Exception as e:
            self.debug_log(f"Error getting previous day todos: {e}")
            return []

    def offer_previous_day_import(self):
        """Offer to import undone todos from previous day."""
        if self.test_mode:
            return  # Skip in test mode
            
        previous_todos = self.get_previous_day_todos()
        
        if not previous_todos:
            return
            
        print("\n" + "="*60)
        print("📅 PREVIOUS DAY TODOS")
        print("="*60)
        print(f"Found {len(previous_todos)} undone todos from yesterday:")
        
        for i, todo in enumerate(previous_todos, 1):
            print(f"  {i}. {todo['text']}")
        
        print("-" * 60)
        
        while True:
            try:
                choice = input("Would you like to import these todos for today? (y/n): ").strip().lower()
                if choice in ['y', 'yes']:
                    # Import all undone todos
                    imported_count = 0
                    for todo in previous_todos:
                        new_todo = {
                            "id": self.todo_counter,
                            "text": todo['text'],
                            "completed": False,
                            "created_at": datetime.now().isoformat(),
                            "imported_from_previous_day": True,
                            "original_date": todo.get('created_at', 'unknown')
                        }
                        self.daily_todos.append(new_todo)
                        self.todo_counter += 1
                        imported_count += 1
                    
                    print(f"✅ Imported {imported_count} todos from yesterday!")
                    break
                elif choice in ['n', 'no']:
                    print("📝 Skipped importing previous day todos.")
                    break
                else:
                    print("Please enter 'y' for yes or 'n' for no.")
            except (EOFError, KeyboardInterrupt):
                print("\n📝 Skipped importing previous day todos.")
                break
        
        print("=" * 60)

    def bring_terminal_to_front(self):
        """Bring the terminal window to front and play notification sound."""
        try:
            if sys.platform == 'darwin':  # macOS
                # Get the terminal app name
                terminal_app = os.environ.get('TERM_PROGRAM', 'Terminal')

                # First play a notification sound to get attention (if not disabled)
                if not self.disable_sound:
                    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)

                # Check if yabai is available for tiling window manager support
                yabai_available = False
                try:
                    subprocess.run(['which', 'yabai'], check=True, capture_output=True)
                    yabai_available = True
                    self.debug_log("Yabai detected - using yabai for window management")
                except subprocess.CalledProcessError:
                    self.debug_log("Yabai not available - using AppleScript")

                success = False

                if yabai_available:
                    # Use yabai to handle window focus across multiple desktops
                    try:
                        # Find terminal windows
                        result = subprocess.run(['yabai', '-m', 'query', '--windows'], 
                                              capture_output=True, text=True, check=True)
                        windows = json.loads(result.stdout)
                        
                        # Look for terminal windows
                        terminal_windows = []
                        for window in windows:
                            app_name = window.get('app', '').lower()
                            if ('terminal' in app_name or 'iterm' in app_name or 
                                terminal_app.lower() in app_name):
                                terminal_windows.append(window)

                        if terminal_windows:
                            # Focus the most recent terminal window
                            target_window = terminal_windows[0]  # First one is usually most recent
                            window_id = target_window['id']
                            space_id = target_window['space']
                            
                            # Switch to the space containing the terminal
                            subprocess.run(['yabai', '-m', 'space', '--focus', str(space_id)], check=True)
                            time.sleep(0.2)  # Give space switch time to complete
                            
                            # Focus the terminal window
                            subprocess.run(['yabai', '-m', 'window', '--focus', str(window_id)], check=True)
                            
                            success = True
                            self.debug_log(f"Focused terminal window {window_id} on space {space_id}")
                        else:
                            # No terminal windows found, create one
                            self.debug_log("No terminal windows found, creating new one")
                            if terminal_app.lower() == 'iterm.app' or 'iterm' in terminal_app.lower():
                                subprocess.run(['open', '-a', 'iTerm'], check=True)
                            else:
                                subprocess.run(['open', '-a', 'Terminal'], check=True)
                            time.sleep(1)  # Give new terminal time to open
                            success = True
                            
                    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
                        self.debug_log(f"Yabai approach failed: {e}")
                        # Fall back to AppleScript
                        yabai_available = False

                # Fall back to AppleScript if yabai isn't available or failed
                if not success and not yabai_available:
                    scripts = [
                        # Approach 1: Simple activate
                        f'''
                        tell application "{terminal_app}"
                            activate
                        end tell
                        ''',
                        
                        # Approach 2: Focus on terminal window and bring all windows
                        f'''
                        tell application "{terminal_app}"
                            activate
                            tell application "System Events"
                                tell process "{terminal_app}"
                                    set frontmost to true
                                    -- Bring all windows to front
                                    set visible to true
                                end tell
                            end tell
                        end tell
                        ''',
                        
                        # Approach 3: Force create new window if needed
                        f'''
                        tell application "{terminal_app}"
                            activate
                            if (count of windows) is 0 then
                                do script ""
                            end if
                            tell application "System Events"
                                tell process "{terminal_app}"
                                    set frontmost to true
                                end tell
                            end tell
                        end tell
                        ''',
                        
                        # Approach 4: Open new terminal window as last resort
                        f'''
                        tell application "{terminal_app}"
                            do script ""
                            activate
                            tell application "System Events"
                                tell process "{terminal_app}"
                                    set frontmost to true
                                end tell
                            end tell
                        end tell
                        '''
                    ]

                    for i, script in enumerate(scripts):
                        try:
                            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
                            success = True
                            self.debug_log(f"Brought {terminal_app} to front using AppleScript approach {i+1}")
                            break
                        except subprocess.CalledProcessError as e:
                            self.debug_log(f"AppleScript approach {i+1} failed: {e}")
                            continue

                # Additional fallback: try opening a new terminal window using `open` command
                if not success:
                    try:
                        if terminal_app.lower() == 'iterm.app' or 'iterm' in terminal_app.lower():
                            subprocess.run(['open', '-a', 'iTerm'], check=True)
                        else:
                            subprocess.run(['open', '-a', 'Terminal'], check=True)
                        success = True
                        self.debug_log("Opened new terminal window using open command")
                    except subprocess.CalledProcessError:
                        pass

                if success:
                    # Give the terminal a moment to open/activate
                    time.sleep(0.5)
                    # Play sound again to ensure attention (if not disabled)
                    if not self.disable_sound:
                        subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)
                else:
                    # If all attempts fail, print visible marker and multiple sounds
                    print("\n" + "="*80)
                    print("🚨 PROCRASTINATION DETECTED - PLEASE SWITCH TO THIS WINDOW 🚨")
                    print("="*80 + "\n")
                    # Play multiple sounds to get attention (if not disabled)
                    if not self.disable_sound:
                        for _ in range(3):
                            subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)
                            time.sleep(0.3)
            else:
                self.debug_log("Window management not implemented for this platform")
                print("\n" + "="*80)
                print("🚨 PROCRASTINATION DETECTED - PLEASE SWITCH TO THIS WINDOW 🚨")
                print("="*80 + "\n")
        except Exception as e:
            print(f"Error in window management: {e}")
            # Fallback to visible marker and sound
            print("\n" + "="*80)
            print("🚨 PROCRASTINATION DETECTED - PLEASE SWITCH TO THIS WINDOW 🚨")
            print("="*80 + "\n")
            if sys.platform == 'darwin' and not self.disable_sound:
                for _ in range(3):
                    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)
                    time.sleep(0.3)

    def start_intervention(self):
        """Start an intervention chat with Gemini using terminal."""
        # Set intervention mode
        self.in_intervention = True
        
        # Bring terminal window to front
        self.bring_terminal_to_front()

        print("\n" + "="*60)
        print("🚨 PRODUCTIVITY INTERVENTION 🚨")
        print("="*60)
        
        # Use encouraging language instead of accusatory
        encouragement = self.get_random_encouragement('intervention_start')
        print(f"💬 {encouragement}")
        
        if self.last_description:
            print(f"\nWhat I observed: {self.last_description}")

        print("\n💬 Chat Commands:")
        print("  • Type 'exit' or 'quit' to end intervention")
        print("  • Type 'endorse' if what you're doing is actually productive")
        print("  • Type 'help' for these commands again")
        print("  • Just chat normally with me to get back on track!")
        print("-" * 60)

        # Keep track of conversation history
        messages = []
        first_interaction = True

        while True:
            try:
                if first_interaction:
                    # Start with user input first
                    print("\nLet's talk! What were you doing?")
                    user_input = self._get_safe_input("\nYou: ")
                    first_interaction = False
                else:
                    # Get user input for continuing conversation
                    user_input = self._get_safe_input("\nYou: ")

                # Handle special commands
                user_lower = user_input.lower().strip()
                if user_lower in ['exit', 'quit', 'q']:
                    print("\n✅ Intervention ended. Let's get back to work!")
                    break
                elif user_lower in ['endorse', 'productive', 'this is productive']:
                    print("\n✅ Got it! I'll note that this activity is productive.")
                    print("Resuming regular monitoring...")
                    break
                elif user_lower in ['help', '?']:
                    print("\n💬 Chat Commands:")
                    print("  • 'exit', 'quit' or 'q' - End intervention")
                    print("  • 'endorse' - Mark current activity as productive")
                    print("  • 'help' or '?' - Show these commands")
                    continue

                # Add user message to history
                messages.append({"role": "user", "content": user_input})

                # Get response from Gemini
                budget_mode = os.getenv('BUDGET_MODE', 'false').lower() == 'true'
                if budget_mode:
                    pro_model = os.getenv('MEDIUM_MODEL', 'google/gemini-2.5-flash')
                else:
                    pro_model = os.getenv('BEST_MODEL', 'google/gemini-2.5-pro')
                
                # Prepare context for first message
                context_prompt = ""
                if len(messages) == 1:  # First user message
                    context_prompt = f"Context: {self.last_description}\n\nThe user was caught procrastinating. They said: '{user_input}'. Help them get back on track with a supportive but motivating response."
                else:
                    context_prompt = user_input

                if self.debug:
                    self.debug_log(f"Sending intervention message to {pro_model}")
                
                # Show loading feedback
                print("💭 Thinking... (waiting for Gemini's response)", end='', flush=True)
                
                # Prepare messages for OpenAI API
                openai_messages = [
                    {"role": "system", "content": intervention_prompt}
                ]
                
                # Add conversation history
                for msg in messages[:-1]:  # All messages except the last one
                    openai_messages.append(msg)
                
                # Add the current user message with context if it's the first message
                openai_messages.append({
                    "role": "user", 
                    "content": context_prompt
                })
                
                # Make the API call with reasoning
                completion = self.client.chat.completions.create(
                    model=pro_model,
                    messages=openai_messages,
                    extra_body={"reasoning": {}}
                )

                # Clear the loading message
                print("\r" + " " * 50 + "\r", end='', flush=True)
                
                gemini_response = completion.choices[0].message.content
                print(f"🤖 Gemini: {gemini_response}")

                # Add Gemini's response to conversation history
                messages.append({"role": "assistant", "content": gemini_response})

                if self.debug:
                    self.debug_log("Updated conversation history:", messages)

            except KeyboardInterrupt:
                print("\n\n✅ Intervention ended (Ctrl+C). Let's get back to work!")
                break
            except Exception as e:
                print(f"\n❌ Error during chat: {e}")
                print("Let's try again or type 'exit' to end intervention.")
                continue

        # Clean up intervention state
        self.in_intervention = False
        
        # Clear any remaining input from the queue
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
        
        print("\n" + "="*60)
        print("✅ Intervention complete. Resuming productivity monitoring...")
        print("="*60)

    def _get_safe_input(self, prompt):
        """Get user input during intervention without conflicts."""
        try:
            # Print the prompt and wait for input
            print(prompt, end='', flush=True)
            
            # Wait for input from the queue (the input thread will handle it)
            while True:
                try:
                    user_input = self.input_queue.get(timeout=0.5)
                    return user_input.strip()
                except queue.Empty:
                    # Continue waiting, but check if we should stop
                    if self.stop_monitoring:
                        return "exit"
                    continue
                    
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C or Ctrl+D gracefully
            return "exit"
        except Exception as e:
            self.debug_log(f"Error getting user input: {e}")
            return "exit"

    def input_thread(self):
        """Separate thread to handle user input without blocking."""
        while not self.stop_monitoring:
            try:
                user_input = input()
                
                # During intervention, always put input in queue
                # During normal monitoring, handle 'x' commands directly
                if self.in_intervention:
                    self.input_queue.put(user_input)
                else:
                    # Handle commands during normal monitoring
                    if user_input.lower().startswith("x "):
                        self.input_queue.put(user_input)
                    elif user_input.lower() in ["end", "end workday", "finish", "stop workday"]:
                        self.input_queue.put("end_workday")
                    elif user_input.lower() in ["summary", "status", "progress"]:
                        self.input_queue.put("get_summary")
                    elif user_input.lower() in ["todos", "todo", "list"]:
                        self.input_queue.put("show_todos")
                    elif user_input.lower().startswith("done "):
                        self.input_queue.put(user_input)
                    elif user_input.lower().startswith("add "):
                        self.input_queue.put(user_input)
                    elif user_input.lower().startswith("pomodoro "):
                        self.input_queue.put(user_input)
                    elif user_input.lower() in ["pomodoro", "timer", "timer status"]:
                        self.input_queue.put("pomodoro_status")
                    elif user_input.lower().startswith("break "):
                        self.input_queue.put(user_input)
                    elif user_input.lower() in ["break", "break status"]:
                        self.input_queue.put("break_status")
                    else:
                        # For other inputs during monitoring, just put in queue
                        self.input_queue.put(user_input)
                        
            except EOFError:
                break
            except Exception:
                # Ignore any other input errors
                pass

    def wait_with_input_check(self, seconds):
        """Wait for specified seconds but check for user input periodically."""
        start_time = time.time()

        while time.time() - start_time < seconds and not self.stop_monitoring:
            # Check for input every 0.5 seconds
            try:
                user_input = self.input_queue.get(timeout=0.5)

                # Handle x command for exceptions
                if user_input.lower().startswith("x "):
                    exception_text = user_input[2:].strip()
                    if exception_text:
                        self.productivity_exceptions.append(exception_text)
                        print(f"Added exception: '{exception_text}'")
                        print(f"Total exceptions: {len(self.productivity_exceptions)}")
                    else:
                        print("No exception text provided after 'x '")
                
                # Handle end workday command
                elif user_input == "end_workday":
                    self.end_workday()
                    return False  # Signal to exit the wait loop
                
                # Handle summary command
                elif user_input == "get_summary":
                    self.generate_hourly_summary()

                # Handle todo commands
                elif user_input == "show_todos":
                    self.show_todos()
                
                elif user_input.lower().startswith("done "):
                    try:
                        todo_id = int(user_input[5:].strip())
                        self.complete_todo(todo_id)
                    except ValueError:
                        print("❌ Invalid todo ID. Use 'done [number]'")
                
                elif user_input.lower().startswith("add "):
                    todo_text = user_input[4:].strip()
                    if todo_text:
                        self.add_todo(todo_text)
                    else:
                        print("❌ No todo text provided. Use 'add [todo text]'")
                
                # Handle pomodoro commands
                elif user_input.lower().startswith("pomodoro "):
                    try:
                        minutes = int(user_input[9:].strip())
                        if 1 <= minutes <= 120:  # Reasonable limit
                            self.start_pomodoro(minutes)
                        else:
                            print("❌ Please enter a time between 1 and 120 minutes")
                    except ValueError:
                        print("❌ Invalid time format. Use 'pomodoro [minutes]' (e.g., 'pomodoro 25')")
                
                elif user_input == "pomodoro_status":
                    self.show_pomodoro_status()
                
                # Handle break commands
                elif user_input.lower().startswith("break "):
                    try:
                        minutes = int(user_input[6:].strip())
                        if 1 <= minutes <= 240:  # Reasonable limit (up to 4 hours)
                            self.start_break(minutes)
                        else:
                            print("❌ Please enter a break time between 1 and 240 minutes")
                    except ValueError:
                        print("❌ Invalid time format. Use 'break [minutes]' (e.g., 'break 15')")
                
                elif user_input == "break_status":
                    self.show_break_status()

            except queue.Empty:
                # No input received, continue waiting
                # Check pomodoro timer every 0.5 seconds for responsive completion notifications
                if self.pomodoro_active:
                    self.check_pomodoro_timer()
                
                # Check break timer every 0.5 seconds for responsive completion notifications
                if self.on_break:
                    self.check_break_timer()
                pass
            except Exception as e:
                self.debug_log(f"Error processing input: {e}")

        return False

    def run(self):
        """Main loop to monitor productivity."""
        if self.test_mode:
            print("🧪 RUNNING IN TEST MODE - Simulating workday activities")
            print(f"Test activities will be generated every {self.interval} seconds...")
        else:
            print(f"ProductivityGuard is running. First check in 30 seconds, then every {self.interval} seconds...")
            print("Note: You may need to grant Screen Recording permission in System Preferences > Security & Privacy > Privacy")

        if OCR_AVAILABLE:
            print(f"OCR enabled using {OCR_TYPE} - text content from screens will be extracted for analysis")
        else:
            print("OCR not available - only visual analysis will be performed")
            print("To enable OCR, install: pip install easyocr (recommended) or pip install pytesseract")

        print("\n🎯 WORKDAY TRACKING ACTIVE")
        print(f"Started: {self.workday_start_time.strftime('%Y-%m-%d %H:%M')}")
        if not self.test_mode:
            print(f"📝 Daily log: {os.path.basename(self.daily_log_file)}")
            print(f"📊 Summary will be saved to: {os.path.basename(self.daily_summary_file)}")
        print("\nCommands during monitoring:")
        print("  x <description> - Add an exception for productive activities")
        print("  Example: x Reading research papers on arxiv.org")
        print("  summary/status/progress - Get current workday summary")
        print("  todos/todo/list - Show current todo list")
        print("  done <number> - Mark todo as completed (e.g., 'done 1')")
        print("  add <text> - Add new todo (e.g., 'add Review code')")
        print("  pomodoro <minutes> - Start a Pomodoro timer (e.g., 'pomodoro 25')")
        print("  pomodoro/timer - Check current timer status")
        print("  break <minutes> - Take a break and pause monitoring (e.g., 'break 15')")
        print("  break - Check current break status")
        print("  end/finish/'end workday' - End workday and get full summary")
        if self.debug:
            print("\nRunning in DEBUG mode - detailed logging enabled")
            print(f"Debug screenshots will be saved to: {self.debug_dir}")

        # Start input monitoring thread
        input_thread = threading.Thread(target=self.input_thread, daemon=True)
        input_thread.start()

        # Wait before first check with input monitoring
        if self.test_mode:
            print("\nStarting test mode immediately...")
            self.wait_with_input_check(2)  # Short wait in test mode
        else:
            print("\nWaiting 30 seconds before first check...")
            self.wait_with_input_check(30)

        while not self.stop_monitoring and self.workday_active:
            try:
                self.debug_log("\n--- Starting new check ---")
                
                # Skip screenshot taking and processing if on break
                if self.on_break:
                    self.debug_log("On break - skipping screenshot and analysis")
                    self.wait_with_input_check(self.interval)
                    continue
                
                if self.test_mode:
                    screenshots, extracted_texts = [], []  # No actual screenshots in test mode
                else:
                    screenshots, extracted_texts = self.take_screenshot()
                
                # Check if workday is active before processing
                if not self.workday_active:
                    break
                
                if screenshots or self.test_mode:
                    if self.test_mode:
                        # Use simulated activities for testing
                        category, description = self.simulate_activity_categorization()
                        print(f"🧪 TEST MODE - Simulated activity: {category.title()} - {description}")
                    else:
                        # Categorize activity instead of just checking procrastination
                        category, description = self.categorize_activity(screenshots, extracted_texts)
                    
                    if category:
                        if not self.test_mode:
                            if self.pomodoro_active:
                                # During pomodoro, show activity more subtly
                                print(f" 📝{category[:3]}", end='', flush=True)
                            else:
                                print(f"\n📝 Activity detected: {category.title()}")
                                if description:
                                    # Truncate long descriptions for cleaner output
                                    clean_desc = description.split('\n')[0].strip()[:100]
                                    if len(clean_desc) < len(description.split('\n')[0].strip()):
                                        clean_desc += "..."
                                    print(f"   Details: {clean_desc}")
                        self.log_activity(category, description)
                        
                        # AI suggestions for todo updates (only occasionally, not every check)
                        if not self.test_mode and self.daily_todos and len(self.activity_log) % 3 == 0:  # Every 3rd check
                            self.suggest_todo_updates(description)
                        
                        # Still check for interventions if it's unproductive
                        unproductive_categories = ['SOCIAL_MEDIA', 'ENTERTAINMENT', 'DISTRACTION']
                        if category in unproductive_categories and not self.test_mode:
                            if self.pomodoro_active:
                                # During pomodoro, show unproductive warning more subtly first
                                print(f" 🚨", end='', flush=True)
                                # But still start intervention since this is important
                                time.sleep(1)  # Brief pause to let user see the timer state
                        
                                print(f"\n\n🚨 Unproductive activity detected: {category.title()}")
                                # Add encouragement message
                                encouragement = self.get_random_encouragement('procrastination')
                                print(f"💬 {encouragement}")
                                self.debug_log("Unproductive activity detected! Starting intervention...")
                                self.start_intervention()
                            else:
                                print(f"\n🚨 Unproductive activity detected: {category.title()}")
                                # Add encouragement message
                                encouragement = self.get_random_encouragement('procrastination')
                                print(f"💬 {encouragement}")
                                self.debug_log("Unproductive activity detected! Starting intervention...")
                                self.start_intervention()
                        elif category in ['CODING', 'STUDYING', 'MEETINGS', 'COMMUNICATION', 'PLANNING', 'WRITING'] and not self.test_mode:
                            # Occasionally show positive reinforcement for productive work
                            current_time = datetime.now()
                            if (current_time - self.last_encouragement_time).total_seconds() > 3600:  # Once per hour
                                encouragement = self.get_random_encouragement('good_work')
                                if self.pomodoro_active:
                                    # During pomodoro, show encouragement more subtly
                                    print(f" 🌟", end='', flush=True)
                                else:
                                    print(f"\n{encouragement}")
                                self.last_encouragement_time = current_time
                    else:
                        self.debug_log("Could not categorize activity")
                
                # Check for hourly summary
                self.check_hourly_summary()
                
                # Check pomodoro timer
                self.check_pomodoro_timer()

                self.debug_log(f"Waiting {self.interval} seconds until next check...")
                print(f"\n⏳ Next check in {self.interval} seconds...\n" + "-"*50)
                self.wait_with_input_check(self.interval)
            except KeyboardInterrupt:
                print("\nProductivityGuard stopped.")
                self.stop_monitoring = True
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                self.wait_with_input_check(self.interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ProductivityGuard - A workday tracking and productivity monitor')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
    parser.add_argument('--test', action='store_true', help='Run in test mode with simulated activities')
    parser.add_argument('--interval', type=int, help='Check interval in seconds (default: 120, test mode: 10)')
    parser.add_argument('--disable-sound', action='store_true', help='Disable notification sounds to prevent popups')
    args = parser.parse_args()
    
    # Set interval for test mode
    interval = args.interval
    if args.test and not interval:
        interval = 10  # Faster interval for testing
    
    guard = ProductivityGuard(interval=interval, debug=args.debug, test_mode=args.test, disable_sound=args.disable_sound)
    guard.run() 
