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
echo "  1. Fill in .env with your personal details and app passwords"
echo "  2. Put your resume in private/resume/ and set RESUME_PATH accordingly"
echo "  3. Activate the virtual environment: source .venv/bin/activate"
echo "  4. Run your first search:  python main.py search"
echo "  5. View results:           python main.py list"
echo "  6. Export to CSV:          python main.py export"
echo "  7. Auto-fill an app:       python main.py apply <ID>"
echo "  8. Run as scheduler:       python main.py daemon"
