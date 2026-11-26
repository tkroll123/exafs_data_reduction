#!/usr/bin/env bash
# Start the EXAFS Data Reduction app: activate the virtual environment,
# start the Flask server and open the page in the browser.
# Usage:  ./start.sh            (stop the server with Ctrl+C)

set -e
cd "$(dirname "$0")"          # run from the folder this script is in
PORT=5050
URL="http://127.0.0.1:$PORT"

# 1. virtual environment (create it on first use)
if [ ! -x .venv/bin/python ]; then
    echo "Creating the virtual environment (.venv) ..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi
source .venv/bin/activate

# 2. already running? then only open the browser
if curl -s -o /dev/null "$URL"; then
    echo "The app is already running at $URL"
else
    # 3. start Flask in the background; stop it when this script ends
    python app.py &
    SERVER=$!
    trap 'kill $SERVER 2>/dev/null' EXIT INT TERM
    for _ in $(seq 1 50); do         # wait up to 10 s for the server
        curl -s -o /dev/null "$URL" && break
        sleep 0.2
    done
fi

# 4. open the browser (Chrome if installed, else the default browser)
if [ "$(uname)" = "Darwin" ]; then
    open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"
elif command -v xdg-open >/dev/null; then
    xdg-open "$URL"
else
    echo "Open $URL in your browser."
fi

# 5. keep running until Ctrl+C (only if this script started the server)
if [ -n "${SERVER:-}" ]; then
    echo "Server running at $URL  -  press Ctrl+C to stop."
    wait $SERVER
fi
