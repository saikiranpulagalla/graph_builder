# graph_builder/utils.py
import re
from typing import Dict, Any

USE_MOCK_EXTRACTION: bool = True

CONTROLLED_RELATIONS = {
    "operates", "offers", "enabled_by", "supported_by", "includes",
    "integrated_with", "executed_via", "acquired", "launched",
    "has_event", "described_in", "related_to", "partnered_with",
}


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