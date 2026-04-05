"""
Utility functions for the trading bot.
"""
import hashlib
import json
import re
from typing import List


def hash_text(text: str) -> str:
    """Create SHA256 hash of text for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove extra whitespace
    text = " ".join(text.split())
    # Remove special characters but keep alphanumeric and basic punctuation
    text = re.sub(r'[^\w\s.,;:\-\'\"]', '', text)
    return text


def extract_sentences(text: str, max_sentences: int = 5) -> str:
    """Extract first N sentences from text."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return " ".join(sentences[:max_sentences])


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def dict_to_json(d: dict) -> str:
    """Convert dict to JSON string."""
    return json.dumps(d)


def json_to_dict(s: str) -> dict:
    """Convert JSON string to dict."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {}


def merge_dicts(*dicts) -> dict:
    """Merge multiple dicts with later ones overriding earlier."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def similarity_score(text1: str, text2: str) -> float:
    """Simple similarity score between two texts (0-1)."""
    # Jaccard similarity on words
    set1 = set(text1.lower().split())
    set2 = set(text2.lower().split())
    
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0
