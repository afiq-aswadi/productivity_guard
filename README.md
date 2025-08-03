**Warning:** 99% written by Claude Code, use at your own risk

# ProductivityGuard

A comprehensive productivity tool that monitors your workday, tracks activities, and provides insights to boost your focus. It detects procrastination and provides supportive coaching while giving you detailed summaries of how you spend your time.

**Note:** This tool is primarily designed for macOS but should work on other platforms.

## What Does It Do?

ProductivityGuard combines activity monitoring with comprehensive workday tracking to help you understand and improve your productivity patterns.

### 🎯 Workday Tracking
- **Activity Categorization**: Automatically categorizes your activities (coding, studying, meetings, breaks, distractions, etc.)
- **Time Tracking**: Tracks how much time you spend on different types of activities
- **Daily Logging**: Creates markdown files to track your activities throughout the day
- **Hourly Updates**: Provides regular progress summaries throughout your workday
- **End-of-Day Summary**: Comprehensive workday analysis with productivity advice and insights
- **File Storage**: Saves daily logs and summaries as dated markdown files for historical tracking

### 🚨 Distraction Detection
If it detects unproductive activities (social media, entertainment sites, etc.), it will:
1. Play a notification sound
2. Bring the terminal window to the front
3. Start a motivational conversation to help you refocus

### 📊 Smart Analytics
- **Productivity Scoring**: Get objective metrics about your focus levels
- **Pattern Recognition**: Identify your most and least productive periods
- **Actionable Insights**: Receive AI-powered recommendations for improvement

## Quick Start

### 1. Get an OpenRouter Account

This app uses OpenRouter to access Google's Gemini AI models. You'll need to:

1. Sign up at [OpenRouter.ai](https://openrouter.ai)
2. Add credit to your account (recommended: $10 to start)
3. Get your API key from the [Keys page](https://openrouter.ai/settings/keys)

**Cost estimate:** Each check costs approximately $0.001-0.002, so $10 should last for thousands of checks.

### 2. Install ProductivityGuard

```bash
# Clone the repository
git clone https://github.com/[your-username]/productivity_guard.git
cd productivity_guard

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up Your API Key

Create a `.env` file in the project directory:

```bash
echo "OPENROUTER_API_KEY=your_api_key_here" > .env
echo "OPENROUTER_APP_NAME=productivity-guard" >> .env
```

Replace `your_api_key_here` with your actual OpenRouter API key.

### 4. Run the App

```bash
# Start workday tracking
python productivity_guard.py

# Run in test mode to try the features
python productivity_guard.py --test

# Enable debug mode for detailed logging
python productivity_guard.py --debug
```

That's it! The app will start tracking your workday and categorizing your activities every 2 minutes (or every 10 seconds in test mode).

## Customizing What's Allowed

The app comes with default rules about what's considered procrastination. You can customize these by editing the prompt files in the `prompts/` directory:

- `prompts/detection_prompt.md` - Controls what activities are allowed/blocked
- `prompts/intervention_prompt.md` - Controls the personality of the AI coach

### For Gemini Users

Some Gemini models may be overly strict about what they consider inappropriate. If Gemini is blocking legitimate work activities, add them to the "Allowed activities" section in `detection_prompt.md`. For example:

```markdown
Allowed activities:
- Your specific work websites
- Research sites you need
- Tools you use for work
```

## Commands

### During Workday Monitoring
- `x <description>` - Add a temporary exception (e.g., `x reading React documentation`)
- `summary`, `status`, or `progress` - Get current workday summary
- `end`, `finish`, or `end workday` - End your workday and get comprehensive summary
- Press `Ctrl+C` - Stop monitoring

### During Intervention (when distraction is detected)
- Type normally to chat with the AI coach
- `exit` - End the conversation and return to monitoring

## Workday Tracking Features

### 📈 Activity Categories
Your activities are automatically categorized into:

**Productive:**
- **Coding**: Programming, IDE usage, debugging
- **Studying**: Documentation, learning materials, research
- **Meetings**: Video calls, collaborative work
- **Communication**: Work-related messaging and email
- **Planning**: Task management, project planning
- **Writing**: Documentation, reports, professional writing

**Neutral:**
- **Breaks**: Food apps, music, brief personal tasks
- **System**: File management, system settings

**Unproductive:**
- **Social Media**: Twitter, Instagram, Facebook, Reddit
- **Entertainment**: YouTube, Netflix, gaming
- **Distraction**: Random browsing, time-wasting sites

### ⏰ Summary Types

**Hourly Updates:** Automatic progress reports showing:
- Current productivity percentage
- Top activities for the hour
- Time breakdown

**End-of-Day Summary:** Comprehensive analysis including:
- Complete time breakdown by category
- Productivity score (1-10)
- Key insights about your work patterns
- Specific recommendations for improvement
- Actionable tips for tomorrow

### 🧪 Testing the Feature

Try the workday tracking in simulation mode:

```bash
# Run the test script
python test_workday_tracking.py

# Or run directly in test mode
python productivity_guard.py --test --interval 5
```

This will simulate various activities and show you how the tracking and summaries work without taking real screenshots.

## 📁 Daily File Logging

ProductivityGuard automatically creates and maintains daily files to track your workday:

### 📝 Daily Activity Logs
- **Location**: `data/logs/YYYY-MM-DD_activity_log.md`
- **Contains**: Real-time activity timeline, hourly summaries, session information
- **Updates**: Continuously throughout the day as activities are detected

### 📊 Daily Summaries  
- **Location**: `data/summaries/YYYY-MM-DD_workday_summary.md`
- **Contains**: Complete time breakdown, productivity metrics, AI analysis and recommendations
- **Created**: When you end your workday with the `end` command

### 🔄 Session Management
- **New Day**: Automatically creates new log file when you start on a new date
- **Resume**: If you restart the program on the same day, it resumes logging to the existing file
- **History**: All previous days' logs and summaries are preserved for historical tracking

### 📋 Example File Structure
```
data/
├── logs/
│   ├── 2024-08-03_activity_log.md
│   ├── 2024-08-04_activity_log.md
│   └── 2024-08-05_activity_log.md
└── summaries/
    ├── 2024-08-03_workday_summary.md
    ├── 2024-08-04_workday_summary.md
    └── 2024-08-05_workday_summary.md
```

The files are automatically excluded from git tracking, so your personal productivity data stays private.

## Troubleshooting

### "No API key found"
Make sure your `.env` file exists and contains your OpenRouter API key.

### Nothing happens when procrastination is detected
On macOS, grant Terminal permission to control your computer:
- System Preferences → Privacy & Security → Accessibility
- Add Terminal (or your terminal app) to the allowed list

### Screenshots not working
You may need to grant screen recording permissions:
- System Preferences → Privacy & Security → Screen Recording
- Add Terminal (or your terminal app) to the allowed list

## Getting Help with the Code

If you want to understand or modify this code, you can:

1. Use [repo2text.com](https://repo2text.com) to convert this repository into a text format
2. Paste the result into any AI assistant (ChatGPT, Claude, etc.)
3. Ask your questions!

## Privacy

- Screenshots are only sent to Google's Gemini AI for analysis
- No data is permanently stored (unless you run in debug mode)
- Your API key is never included in screenshots or logs

## Advanced Usage

For technical details, debugging, and development information, see [TECHNICAL.md](TECHNICAL.md).

## License

This is free and open source software. Feel free to modify it for your personal productivity needs!
