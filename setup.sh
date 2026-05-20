#!/usr/bin/env bash
# One-time setup script for Internship Finder

set -e
echo "Setting up Internship Finder..."

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

python -m playwright install chromium

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your email, profile, and LinkedIn credentials"
echo "  2. Activate the virtual environment: source .venv/bin/activate"
echo "  3. Run your first search:  python main.py search"
echo "  4. View results:           python main.py list"
echo "  5. Export to CSV:          python main.py export"
echo "  6. Auto-fill an app:       python main.py apply <ID>"
echo "  7. Run as scheduler:       python main.py daemon"
