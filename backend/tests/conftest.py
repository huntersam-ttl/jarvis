"""Pytest configuration for the Jarvis backend."""
import os
import sys

# Ensure the backend package is importable when running pytest from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a test environment so no real secrets are required.
os.environ.setdefault("JARVIS_ENV", "test")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o-mini")
