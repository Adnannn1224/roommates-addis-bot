#!/bin/bash
# Copy all files to /app (where Railway runs)
cp -r ./* /app/ 2>/dev/null || true
cp -r ./.git /app/ 2>/dev/null || true

# Go to /app and run bot
cd /app
python bot.py