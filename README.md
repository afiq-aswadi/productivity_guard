**Warning:** 99% written by Claude Code, use at your own risk

# ProductivityGuard

A Python application that helps keep you focused by monitoring your screen for procrastination using Gemini AI. The app takes periodic screenshots, analyzes them for signs of procrastination, and initiates motivational conversations when you get distracted.

## Features

- **Smart Procrastination Detection**: Two-stage detection using Gemini Flash for quick checks and Gemini Pro with reasoning for detailed analysis
- **Multi-Monitor Support**: Captures and analyzes all connected displays
- **Productivity Exceptions**: Add exceptions for legitimate activities (e.g., "x reading documentation for work")
- **OCR Support**: Extracts text from screenshots using EasyOCR or PyTesseract for better content analysis
- **Interactive Interventions**: Engages in motivational conversations when procrastination is detected
- **Debug Mode**: Save screenshots and detailed logs for troubleshooting
- **Configurable Settings**: Customize check intervals and detection sensitivity

## Requirements

- Python 3.8 or higher
- macOS, Windows, or Linux
- OpenRouter API key (for Gemini access)
- Optional: EasyOCR or PyTesseract for text extraction

## Installation

1. Clone this repository:
   ```bash
   git clone [repository-url]
   cd productivity_guard
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root:
   ```
   OPENROUTER_API_KEY=your_api_key_here
   OPENROUTER_APP_NAME=productivity-guard
   ```

5. (Optional) Install OCR support:
   ```bash
   # For EasyOCR (recommended, but larger download)
   pip install easyocr
   
   # For PyTesseract (requires system installation)
   # macOS: brew install tesseract
   # Ubuntu: sudo apt-get install tesseract-ocr
   # Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   pip install pytesseract
   ```

## Usage

### Basic Usage

Start the productivity monitor:
```bash
python productivity_guard.py
```

The app will:
1. Take screenshots every 30 seconds (default)
2. Analyze them for signs of procrastination
3. Start a conversation if procrastination is detected
4. Continue monitoring after the conversation ends

### Commands During Monitoring

While the app is running, you can type:
- `x <description>` - Add a productivity exception (e.g., `x reading Python documentation`)
- `q` or `quit` - Stop monitoring and exit
- `status` - Show current monitoring status

### Commands During Intervention

When in a conversation with Gemini:
- Type your responses normally to continue the conversation
- `exit` - End the intervention and return to monitoring
- The conversation will help you refocus on productive tasks

### Debug Mode

Run with detailed logging and screenshot saving:
```bash
python productivity_guard.py --debug
```

In debug mode:
- Check interval reduced to 10 seconds
- Screenshots saved to `debug_screenshots/` directory
- Detailed API request/response logging
- Performance metrics displayed

## Configuration

You can customize the behavior by modifying these parameters in the code:

- `interval` (default: 30): Seconds between checks
- `ocr_library` (default: None): Set to 'easyocr' or 'pytesseract' for text extraction
- Flash model threshold for initial detection
- Pro model reasoning prompts

## Testing

The project includes a comprehensive test suite with 100% code coverage goals.

### Run Tests

```bash
# Run with coverage report
python run_tests.py

# Run specific test module
python -m unittest test_productivity_guard.TestProductivityGuard

# Run with verbose output
python -m unittest discover -v
```

### Test Coverage

The test suite includes:
- Unit tests for all core functionality
- Mock-based testing for external dependencies
- Integration tests for the full monitoring cycle
- Screenshot capture simulation
- LLM response mocking
- User interaction testing

## Architecture

### Core Components

1. **ProductivityGuard**: Main class orchestrating the monitoring process
2. **LLM Integration**: Uses neels-utils for Gemini API access via OpenRouter
3. **Screenshot Capture**: Cross-platform screenshot functionality
4. **OCR Processing**: Optional text extraction for better content analysis
5. **Two-Stage Detection**:
   - Stage 1: Gemini Flash for quick binary classification
   - Stage 2: Gemini Pro with reasoning for detailed analysis

### How It Works

1. **Screenshot Capture**: Takes screenshots of all monitors
2. **Initial Check**: Gemini Flash quickly determines if the content might be procrastination
3. **Detailed Analysis**: If flagged, Gemini Pro analyzes with reasoning to confirm
4. **Intervention**: Starts an interactive conversation to help refocus
5. **Exception Handling**: Respects user-defined productivity exceptions

## Troubleshooting

### Common Issues

1. **"No API key found"**: Ensure your `.env` file contains `OPENROUTER_API_KEY`
2. **Screenshot errors**: Check screen recording permissions (especially on macOS)
3. **OCR not working**: Verify OCR library installation and system dependencies
4. **High CPU usage**: Increase the check interval or disable OCR

### Debug Tips

1. Run in debug mode to see detailed logs
2. Check `debug_screenshots/` to verify what the AI sees
3. Review intervention descriptions to understand detection reasoning
4. Test with known procrastination sites to verify detection

## Privacy & Security

- Screenshots are processed locally and sent only to the Gemini API
- No data is stored permanently unless debug mode is enabled
- API keys are never logged or included in screenshots
- All communications use HTTPS

## Development

### Project Structure

```
productivity_guard/
├── productivity_guard.py    # Main application
├── test_productivity_guard.py # Test suite
├── run_tests.py            # Test runner with coverage
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .env                   # API keys (not in git)
├── .gitignore            # Git ignore rules
└── debug_screenshots/     # Debug mode screenshots
```

### Adding Features

1. Follow the existing code patterns
2. Add comprehensive tests for new functionality
3. Update this README with new features
4. Ensure all tests pass before committing

### Code Style

- Follow PEP 8 Python style guidelines
- Add type hints for function parameters
- Include docstrings for all public methods
- Keep functions focused and testable

## License

This project is for personal use. Modify and extend as needed for your productivity needs.

## Acknowledgments

- Uses Gemini AI models via OpenRouter for content analysis
- Built with neels-utils for LLM operations
- Inspired by the need to stay focused in a distraction-filled digital world
