#!/bin/bash
# Helper script to pull latest PPM Organic Farms updates on PythonAnywhere
echo '==> Resetting local database changes...'
git checkout market.db 2>/dev/null || true
git stash
echo '==> Pulling latest updates from GitHub...'
git pull origin main
echo '==> Successfully updated to latest commit!'
echo '==> Please go to your PythonAnywhere Web tab and click the green Reload button.'
