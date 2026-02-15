# graph_builder/utils.py
import re
from typing import Dict, Any

USE_MOCK_EXTRACTION: bool = True

CONTROLLED_RELATIONS = {
    "operates", "offers", "enabled_by", "supported_by", "includes",
    "integrated_with", "executed_via", "acquired", "launched",
    "has_event", "described_in", "partnered_with",
}


def normalize_for_comparison(name: str) -> str:
    """
    Normalize entity name for alias detection.
    Converts to lowercase, removes punctuation, strips whitespace.
    Example: "Nimbus Solutions" -> "nimbussolutions"
    """
    if not name:
        return ""
    # Lowercase and remove all non-alphanumeric characters
    normalized = re.sub(r'[^a-z0-9]', '', name.lower())
    return normalized


def is_alias(name1: str, name2: str) -> bool:
    """
    Check if two names are aliases of the same entity.
    Returns True if one is a substring of the other after normalization.
    Example: "Nimbus" and "Nimbus Solutions" are aliases.
    """
    if not name1 or not name2:
        return False
    
    norm1 = normalize_for_comparison(name1)
    norm2 = normalize_for_comparison(name2)
    
    if norm1 == norm2:
        return True
    
    # Check if one is contained in the other (handles "Nimbus" vs "Nimbus Solutions")
    if norm1 in norm2 or norm2 in norm1:
        # Ensure it's not a coincidental substring (require significant overlap)
        min_len = min(len(norm1), len(norm2))
        if min_len >= 4:  # Minimum 4 characters for alias detection
            return True
    
    return False


def is_invalid_entity_name(name: str) -> bool:
    """
    Check if a name is invalid (verb, sentence fragment, etc.).
    Returns True if the name should be rejected.
    """
    if not name or len(name) < 3:
        return True
    
    lower = name.lower().strip()
    
    # Reject common verbs and sentence fragments
    invalid_patterns = {
        "founded", "launched", "rolled out", "focuses on", "established",
        "created", "started", "began", "introduced", "announced",
        "provides", "offers", "delivers", "enables", "supports"
    }
    
    if lower in invalid_patterns:
        return True
    
    # Reject if it starts with a verb
    verb_prefixes = ["founded", "launched", "rolled", "focuses", "established"]
    if any(lower.startswith(v) for v in verb_prefixes):
        return True
    
    return False


def normalize_entity_label(name: str) -> str:
    """
    Normalize entity label for deduplication.
    Strips common suffixes (Inc, Corp, Ltd, Co) to match variants.
    Example: "AgroSupply Co" -> "AgroSupply"
    """
    if not name:
        return ""
    name = name.strip()
    # Remove common company suffixes
    suffixes = r'(?:Inc\.?|Corp\.?|LLC|Ltd\.?|Co\.?|Corporation)'
    normalized = re.sub(rf'\s+{suffixes}\.?\s*$', '', name, flags=re.IGNORECASE)
    return normalized.strip()


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", name.lower().strip())


def clean_company_name(name: str) -> str:
    """Remove common suffixes from company names."""
    if not name:
        return ""
    name = name.strip()
    suffixes = r'(?:Inc\.?|Corp\.?|LLC|Ltd\.?|Co\.?|Corporation)'
    name = re.sub(rf'\s+{suffixes}\.?\s*$', '', name, flags=re.IGNORECASE)
    return name.strip()


def clean_entity_name(name: str) -> str:
    """
    Lightweight entity name cleanup - removes trailing clauses.
    Removes text after common clause markers: "to", "for", "which", "that"
    Example: "VectorSys to strengthen..." -> "VectorSys"
    """
    if not name:
        return ""
    name = name.strip()
    # Split on clause markers and take first part
    parts = re.split(r'\s+\b(to|for|which|that)\b\s+', name, maxsplit=1, flags=re.IGNORECASE)
    return parts[0].strip()


def is_likely_company(name: str) -> bool:
    """Relaxed but safe filter — allows TechNova, OpenAI, QuantumAI, etc."""
    if not name or len(name) < 4:
        return False
    lower = name.lower()
    bad = {"san", "francisco", "this", "the", "company", "headquartered", "in", "a", "new", "its"}
    if any(w in lower.split() for w in bad):
        return False
    # Single-word brands (TechNova, QuantumAI, etc.)
    if " " not in name:
        return len(name) >= 5 and name[0].isupper()
    return True


def generate_id(label: str, node_type: str) -> str:
    norm = normalize_name(label)
    return f"{node_type.lower()}_{norm}"


def choose_best_label(labels: list[str]) -> str:
    """
    Choose the most descriptive label from a list of aliases.
    Prefers longer, more specific names.
    Example: ["Nimbus", "Nimbus Solutions"] -> "Nimbus Solutions"
    """
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    
    # Sort by length (descending) and alphabetically for determinism
    sorted_labels = sorted(labels, key=lambda x: (-len(x), x))
    return sorted_labels[0]