# Function to activate ProductivityGuard
guard() {
    # Store the absolute path to ProductivityGuard
    GUARD_PATH="$HOME/Code/Big Claude/productivity_guard"
    
    # Check if the directory exists
    if [ ! -d "$GUARD_PATH" ]; then
        echo "Error: ProductivityGuard directory not found at $GUARD_PATH"
        return 1
    fi
    
    # Navigate to the directory
    cd "$GUARD_PATH"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Virtual environment not found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi
    
    # Run ProductivityGuard
    echo "Starting ProductivityGuard..."
    python productivity_guard.py "$@"
} 