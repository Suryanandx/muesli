#!/bin/bash
set -e

echo ""
echo "  🥣 muesli setup"
echo "  ─────────────────────────────"

# .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  ✓ Created .env (add your ANTHROPIC_API_KEY)"
else
  echo "  ✓ .env already exists"
fi

# Virtualenv
if [ ! -d .venv ]; then
  python3 -m venv .venv
  echo "  ✓ Created .venv"
fi

# Dependencies
echo "  Installing dependencies..."
.venv/bin/pip install -r requirements.txt -q
echo "  ✓ Dependencies installed"

# Optional: BlackHole for system audio
if command -v brew &>/dev/null; then
  if brew list blackhole-2ch &>/dev/null 2>&1; then
    echo "  ✓ BlackHole 2ch detected"
  else
    echo ""
    echo "  Tip: install BlackHole to capture Zoom/Meet/Teams audio:"
    echo "    brew install blackhole-2ch"
    echo "    Then set AUDIO_DEVICE=BlackHole 2ch in .env"
  fi
fi

echo ""
echo "  Setup complete!"
echo "  ─────────────────────────────"
echo "  1. Add ANTHROPIC_API_KEY to .env"
echo "  2. Run:  .venv/bin/python -m app.main"
echo "  3. Open: http://localhost:7474"
echo ""
