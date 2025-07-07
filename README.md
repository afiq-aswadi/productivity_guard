# ProductivityGuard

A friendly AI assistant that helps you stay focused by monitoring your screen for procrastination. When it detects you're getting distracted, it starts a supportive conversation to help you get back on track.

**Note:** This tool is primarily designed for macOS but should work on other platforms.

## What Does It Do?

ProductivityGuard takes periodic screenshots of your screens and uses Google's Gemini AI to check if you're procrastinating. If it detects distraction (social media, entertainment sites, etc.), it will:

1. Play a notification sound
2. Bring the terminal window to the front
3. Start a motivational conversation to help you refocus

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
python productivity_guard.py
```

That's it! The app will start monitoring your screens every 30 seconds.

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

### During Monitoring
- `x <description>` - Add a temporary exception (e.g., `x reading React documentation`)
- `status` - Check if monitoring is active
- `q` or `quit` - Stop the app

### During Intervention
- Type normally to chat with the AI coach
- `exit` - End the conversation and return to monitoring

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