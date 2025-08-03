import os
import time
import tempfile
from datetime import datetime
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
    def __init__(self, interval=None, debug=False):
        """Initialize ProductivityGuard with a checking interval in seconds."""
        # LLMClient will automatically use OPENROUTER_API_KEY from environment

        # Get interval from environment or use default
        self.interval = interval or int(os.getenv('CHECK_INTERVAL', 120))
        if debug:
            self.interval = 10  # Override interval in debug mode

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

        # Initialize OCR reader if available
        self.ocr_reader = None
        if OCR_AVAILABLE:
            try:
                if OCR_TYPE == "easyocr":
                    self.ocr_reader = easyocr.Reader(['en'])
                    self.debug_log("EasyOCR initialized successfully")
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
        print("\nTaking screenshot...")  # Always print this message
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

            # Print the decision
            print(f"Decision ({model_name}): {'Procrastinating' if is_procrastinating else 'Working'}")

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
        
        # Step 2: Flash detected procrastination, verify with Pro + reasoning
        pro_model = os.getenv('BEST_MODEL', 'google/gemini-2.5-pro')
        self.debug_log("Step 2: Flash detected procrastination, verifying with Pro + reasoning...")
        
        pro_result, pro_response = self._check_with_model(
            screenshots, extracted_texts, pro_model, 
            use_reasoning=True, print_reasoning=False
        )
        
        # Always print Pro's response
        print(f"\nPro (Gemini 2.5) response: {pro_response}")
        
        if pro_result:
            self.debug_log("Both Flash and Pro agree: procrastination detected!")
        else:
            self.debug_log("Pro disagrees with Flash: not procrastinating")
            
        return pro_result

    def bring_terminal_to_front(self):
        """Bring the terminal window to front and play notification sound."""
        try:
            if sys.platform == 'darwin':  # macOS
                # Get the terminal app name
                terminal_app = os.environ.get('TERM_PROGRAM', 'Terminal')

                # First play a notification sound to get attention
                subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)

                # Try different approaches to bring terminal to front
                scripts = [
                    # Approach 1: Simple activate
                    f'''
                    tell application "{terminal_app}"
                        activate
                    end tell
                    ''',
                    
                    # Approach 2: Focus on terminal window
                    f'''
                    tell application "{terminal_app}"
                        activate
                        tell application "System Events"
                            tell process "{terminal_app}"
                                set frontmost to true
                            end tell
                        end tell
                    end tell
                    ''',
                    
                    # Approach 3: Try to bring window to front without minimizing others
                    f'''
                    tell application "System Events"
                        tell process "{terminal_app}"
                            set frontmost to true
                        end tell
                    end tell
                    '''
                ]

                success = False
                for script in scripts:
                    try:
                        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
                        success = True
                        break
                    except subprocess.CalledProcessError:
                        continue

                if success:
                    self.debug_log(f"Brought {terminal_app} to front")
                else:
                    # If all window management attempts fail, at least print a visible marker
                    print("\n" + "="*80)
                    print("PROCRASTINATION DETECTED - PLEASE SWITCH TO THIS WINDOW")
                    print("="*80 + "\n")
                    # Play the sound again to ensure it gets attention
                    subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)
            else:
                self.debug_log("Window management not implemented for this platform")
                print("\n" + "="*80)
                print("PROCRASTINATION DETECTED - PLEASE SWITCH TO THIS WINDOW")
                print("="*80 + "\n")
        except Exception as e:
            print(f"Error in window management: {e}")
            # Fallback to visible marker and sound
            print("\n" + "="*80)
            print("PROCRASTINATION DETECTED - PLEASE SWITCH TO THIS WINDOW")
            print("="*80 + "\n")
            if sys.platform == 'darwin':
                subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'], check=False)

    def start_intervention(self):
        """Start an intervention chat with Gemini using terminal."""
        # Set intervention mode
        self.in_intervention = True
        
        # Bring terminal window to front
        self.bring_terminal_to_front()

        print("\n" + "="*60)
        print("🚨 PRODUCTIVITY INTERVENTION 🚨")
        print("="*60)
        print("You've been caught procrastinating! Let's have a quick chat.")
        
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
                    # Handle 'x' commands during normal monitoring
                    if user_input.lower().startswith("x "):
                        self.input_queue.put(user_input)
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

                # Handle x  command for exceptions
                if user_input.lower().startswith("x "):
                    exception_text = user_input[2:].strip()
                    if exception_text:
                        self.productivity_exceptions.append(exception_text)
                        print(f"Added exception: '{exception_text}'")
                        print(f"Total exceptions: {len(self.productivity_exceptions)}")
                    else:
                        print("No exception text provided after 'x '")

            except queue.Empty:
                # No input received, continue waiting
                pass
            except Exception as e:
                self.debug_log(f"Error processing input: {e}")

        return False

    def run(self):
        """Main loop to monitor productivity."""
        print(f"ProductivityGuard is running. First check in 30 seconds, then every {self.interval} seconds...")
        print("Note: You may need to grant Screen Recording permission in System Preferences > Security & Privacy > Privacy")

        if OCR_AVAILABLE:
            print(f"OCR enabled using {OCR_TYPE} - text content from screens will be extracted for analysis")
        else:
            print("OCR not available - only visual analysis will be performed")
            print("To enable OCR, install: pip install easyocr (recommended) or pip install pytesseract")

        print("\nCommands during monitoring:")
        print("  x <description> - Add an exception for productive activities")
        print("  Example: x Reading research papers on arxiv.org")
        if self.debug:
            print("\nRunning in DEBUG mode - detailed logging enabled")
            print(f"Debug screenshots will be saved to: {self.debug_dir}")

        # Start input monitoring thread
        input_thread = threading.Thread(target=self.input_thread, daemon=True)
        input_thread.start()

        # Wait 30 seconds before first check with input monitoring
        print("\nWaiting 30 seconds before first check...")
        self.wait_with_input_check(30)

        while not self.stop_monitoring:
            try:
                self.debug_log("\n--- Starting new check ---")
                screenshots, extracted_texts = self.take_screenshot()
                if screenshots and self.check_procrastination(screenshots, extracted_texts):
                    self.debug_log("Procrastination detected! Starting intervention...")
                    self.start_intervention()
                else:
                    self.debug_log("No procrastination detected")

                self.debug_log(f"Waiting {self.interval} seconds until next check...")
                self.wait_with_input_check(self.interval)
            except KeyboardInterrupt:
                print("\nProductivityGuard stopped.")
                self.stop_monitoring = True
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                self.wait_with_input_check(self.interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ProductivityGuard - A Gemini-powered productivity monitor')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
    args = parser.parse_args()
    
    guard = ProductivityGuard(debug=args.debug)
    guard.run() 
