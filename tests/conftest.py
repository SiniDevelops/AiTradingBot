"""
Pytest configuration and fixtures.
"""
import os
import sys
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Ensure app module is available
from app import db

# Marker for asyncio tests
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
