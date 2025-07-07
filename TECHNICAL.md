# Technical Documentation - ProductivityGuard

This document contains detailed technical information about ProductivityGuard's architecture, implementation, and development.

## Architecture Overview

### Core Components

1. **ProductivityGuard Class**: Main orchestrator for the monitoring process
2. **LLM Integration**: Uses neels-utils library for Gemini API access via OpenRouter
3. **Screenshot Capture**: Cross-platform screenshot functionality using `mss` library
4. **OCR Processing**: Optional text extraction using EasyOCR or PyTesseract
5. **Two-Stage Detection**:
   - Stage 1: Gemini Flash for quick binary classification
   - Stage 2: Gemini Pro with reasoning for detailed analysis

### Detection Flow

1. **Screenshot Capture**: Takes screenshots of all monitors
2. **Initial Check**: Gemini Flash quickly determines if content might be procrastination
3. **Detailed Analysis**: If flagged, Gemini Pro analyzes with reasoning to confirm
4. **Intervention**: Starts an interactive conversation to help refocus
5. **Exception Handling**: Respects user-defined productivity exceptions

## Configuration Options

### Environment Variables

- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `OPENROUTER_APP_NAME`: Application name for tracking (default: productivity-guard)
- `CHECK_INTERVAL`: Seconds between checks (default: 120)
- `MEDIUM_MODEL`: Flash model for quick checks (default: google/gemini-2.5-flash-preview-05-20)
- `BEST_MODEL`: Pro model for detailed analysis (default: google/gemini-2.5-pro)

### Code Parameters

In `productivity_guard.py`:
- `interval`: Check frequency in seconds
- `ocr_library`: Set to 'easyocr' or 'pytesseract' for text extraction
- Flash model threshold for initial detection
- Pro model reasoning prompts

## Debug Mode

Run with `--debug` flag for:
- Check interval reduced to 10 seconds
- Screenshots saved to `debug_screenshots/` directory
- Detailed API request/response logging
- Performance metrics displayed

```bash
python productivity_guard.py --debug
```

## Testing

### Test Suite

The project includes comprehensive tests with 100% code coverage goals:

```bash
# Run with coverage report
python run_tests.py

# Run specific test module
python -m unittest test_productivity_guard.TestProductivityGuard

# Run with verbose output
python -m unittest discover -v
```

### Test Coverage

- Unit tests for all core functionality
- Mock-based testing for external dependencies
- Integration tests for the full monitoring cycle
- Screenshot capture simulation
- LLM response mocking
- User interaction testing

## Project Structure

```
productivity_guard/
├── productivity_guard.py      # Main application
├── test_productivity_guard.py # Test suite
├── run_tests.py              # Test runner with coverage
├── requirements.txt          # Python dependencies
├── README.md                 # User documentation
├── TECHNICAL.md              # This file
├── prompts/                  # Customizable AI prompts
│   ├── detection_prompt.md   # Procrastination detection rules
│   └── intervention_prompt.md # AI coach personality
├── .env                      # API keys (not in git)
├── .gitignore               # Git ignore rules
└── debug_screenshots/        # Debug mode screenshots

```

## Dependencies

### Core Dependencies
- `llm-utils` / `neels-utils`: LLM operations wrapper
- `mss`: Cross-platform screenshot capture
- `Pillow`: Image processing
- `python-dotenv`: Environment variable management

### Optional Dependencies
- `easyocr`: Advanced OCR (larger download, better accuracy)
- `pytesseract`: Lightweight OCR (requires system Tesseract installation)

## Performance Considerations

### Resource Usage
- CPU: Minimal during idle, spike during screenshot/OCR processing
- Memory: ~200MB base, up to 1GB with EasyOCR loaded
- Network: API calls only during checks (minimal bandwidth)

### Optimization Tips
- Increase check interval for lower resource usage
- Disable OCR if not needed
- Use Flash model only for faster, cheaper checks

## Security Considerations

### Data Handling
- Screenshots processed in memory, not persisted (except debug mode)
- API communications use HTTPS
- No telemetry or external logging

### API Key Security
- Keys loaded from `.env` file
- Never included in logs or screenshots
- Not transmitted except to OpenRouter

## Development Guide

### Adding Features

1. Follow existing code patterns
2. Add comprehensive tests for new functionality
3. Update documentation
4. Ensure all tests pass

### Code Style

- PEP 8 Python style guidelines
- Type hints for function parameters
- Docstrings for all public methods
- Functions should be focused and testable

### Prompt Customization

Prompts are loaded from markdown files in the `prompts/` directory:
- Edit prompts without changing code
- OCR note is dynamically added if OCR is available
- Prompts are loaded once at startup

### Error Handling

The app includes robust error handling for:
- Missing API keys
- Screenshot capture failures
- OCR processing errors
- Network connectivity issues
- LLM API errors

## API Usage and Costs

### OpenRouter Pricing (approximate)
- Gemini Flash: ~$0.0001 per check
- Gemini Pro: ~$0.001 per detailed analysis
- Typical usage: $1-2 per month with default settings

### Reducing Costs
- Increase check interval
- Adjust Flash model sensitivity
- Disable Pro model confirmation
- Use exceptions for known productive activities

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure virtual environment is activated
2. **Permission errors**: Check system permissions for screen recording
3. **High CPU with OCR**: Normal for EasyOCR first load, consider PyTesseract
4. **API errors**: Verify API key and OpenRouter credit balance

### Debug Techniques

1. Use `--debug` flag for detailed logging
2. Check `debug_screenshots/` to see what AI analyzes
3. Review API responses in debug output
4. Test with known procrastination sites

## Contributing

When contributing:
1. Write tests for new features
2. Update both README.md and TECHNICAL.md
3. Follow existing code style
4. Test on multiple platforms if possible
5. Keep security in mind