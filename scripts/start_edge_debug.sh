#!/usr/bin/env bash
# Closes existing Edge instances and restarts Edge with remote debugging enabled
# so the testing framework can connect to it via CDP without closing your session.

echo "Closing existing Microsoft Edge instances..."
osascript -e 'quit app "Microsoft Edge"'
sleep 2

echo "Starting Microsoft Edge with remote debugging on port 9222..."
open -a "Microsoft Edge" --args --remote-debugging-port=9222
