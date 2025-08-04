# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProductivityGuard is a Python-based workday monitoring and productivity tracking application that combines:
- Real-time activity monitoring via screenshots and AI analysis
- Workday tracking with automatic activity categorization
- Daily todo list management with smart completion tracking
- AI-powered intervention system for distraction management
- Comprehensive daily logging and summary generation

## Development Commands

### Testing
```bash
# Run all tests with coverage report
python run_tests.py

# Run specific test modules
python -m unittest test_productivity_guard.TestProductivityGuard
python -m unittest test_daily_logging
python -m unittest test_workday_tracking

# Run tests with verbose output
python -m unittest discover -v
```

### Running the Application
```bash
# Normal operation (120 second intervals)
python productivity_guard.py

# Debug mode (10 second intervals, saves screenshots, detailed logging)
python productivity_guard.py --debug

# Test mode (simulated activities, 10 second intervals)
python productivity_guard.py --test

# Disable sound notifications
python productivity_guard.py --disable-sound

# Custom interval
python productivity_guard.py --interval 60
```

### Demo Scripts
```bash
# Demo todo list features
python demo_todo_features.py
python demo_new_todo_features.py

# Demo workday tracking features
python demo_workday_tracking.py

# Demo complete feature set
python demo_complete_features.py

# Test specific components
python test_daily_logging.py
python test_workday_tracking.py
```

### Virtual Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Architecture Overview

### Core Components

1. **ProductivityGuard Class** (`productivity_guard.py:86`): Main orchestrator that manages the monitoring lifecycle
2. **Two-Stage AI Detection System**:
   - Stage 1: Gemini Flash for quick binary classification
   - Stage 2: Gemini Pro with reasoning for detailed analysis
3. **DailyTodoManager**: Handles todo list persistence and smart completion tracking
4. **WorkdayTracker**: Manages activity categorization and time tracking
5. **DailyLogger**: Creates and maintains daily activity logs and summaries

### Key Data Flow

1. **Screenshot Capture**: Uses `mss` library for cross-platform multi-monitor screenshots
2. **OCR Processing**: Optional text extraction using EasyOCR or PyTesseract
3. **AI Analysis**: OpenRouter API calls to Gemini models for activity classification
4. **Data Persistence**: JSON files for todos, markdown files for logs/summaries
5. **User Interaction**: Command-line interface with real-time commands

### File Structure Patterns

```
data/
├── YYYY-MM-DD_daily_todos.json    # Daily todo persistence
├── logs/YYYY-MM-DD_activity_log.md # Real-time activity logging
└── summaries/YYYY-MM-DD_workday_summary.md # End-of-day summaries

prompts/
├── detection_prompt.md             # AI rules for procrastination detection
├── intervention_prompt.md          # AI personality for coaching
├── activity_categorization_prompt.md # Rules for activity categorization
└── workday_summary_prompt.md       # End-of-day summary generation
```

## Key Implementation Details

### AI Model Configuration
- Uses OpenRouter API with environment variables for model selection
- Default models: `google/gemini-2.5-flash-preview-05-20` (fast) and `google/gemini-2.5-pro` (detailed)
- Configurable via `MEDIUM_MODEL` and `BEST_MODEL` environment variables

### Activity Categories
- **Productive**: coding, studying, meetings, communication, planning, writing
- **Neutral**: breaks, system tasks
- **Unproductive**: social media, entertainment, distractions

### Todo List Features
- Smart completion detection using AI analysis of current activity
- Automatic daily file rotation
- Integration with workday tracking for productivity insights
- Command-line interface for real-time management

### Error Handling
- Robust handling of API failures, screenshot capture issues, and permission problems
- Graceful degradation when OCR libraries are unavailable
- Apple Silicon MPS compatibility fixes for PyTorch/EasyOCR

## Environment Configuration

Required environment variables (`.env` file):
```bash
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_APP_NAME=productivity-guard
DISABLE_SOUND=false  # Set to true to prevent notification popups
CHECK_INTERVAL=120   # Default check interval in seconds
```

## Testing Architecture

- Comprehensive test suite with mock-based testing for external dependencies
- 100% code coverage goal with coverage reporting via `run_tests.py`
- Integration tests for the full monitoring cycle
- Screenshot simulation and LLM response mocking for deterministic testing

## Common Development Patterns

- All AI prompts loaded from markdown files in `prompts/` directory for easy customization
- Cross-platform compatibility handled via conditional imports and OS detection
- Thread-safe operations for concurrent screenshot processing and user interaction
- Extensive logging with debug mode for troubleshooting