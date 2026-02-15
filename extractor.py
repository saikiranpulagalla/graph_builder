# graph_builder/extractor.py
import re
from typing import Dict, Any, List
from .utils import USE_MOCK_EXTRACTION, clean_company_name, is_likely_company, clean_entity_name


def extract(chunk_text: str, chunk_id: str, page: int) -> Dict[str, Any]:
    """
    Rule-based extraction is intentionally lossy.
    Graph builder enforces normalization, precedence, and provenance
    to ensure structural correctness.
    """
    if not USE_MOCK_EXTRACTION:
        return {"entities": [], "relations": [], "events": []}

    entities: List[Dict] = []
    relations: List[Dict] = []
    events: List[Dict] = []
    seen: set[str] = set()

    # ── SPECIFIC ENTITIES FIRST (they win) ─────────────────────────────
    for m in re.findall(r"partnered with ([A-Z][A-Za-z0-9\s&]+)", chunk_text, re.IGNORECASE):
        name = clean_entity_name(m.strip())  # Clean trailing clauses
        if name and name not in seen:
            entities.append({"name": name, "type": "Partner", "attributes": {}})
            seen.add(name)

    # Match: "platform called X", "platform named X", etc.
    for m in re.findall(r"(?:cloud\s+)?platform\s+(?:called|named)\s+([A-Z][A-Za-z0-9]+)", chunk_text, re.IGNORECASE):
        name = m.strip()
        if name and name not in seen:
            entities.append({"name": name, "type": "Platform", "attributes": {}})
            seen.add(name)

    for m in re.findall(r"launched (?:its |the )?([A-Z][^.,;]+?service)", chunk_text, re.IGNORECASE):
        name = m.strip()
        if name and name not in seen:
            entities.append({"name": name, "type": "Service", "attributes": {}})
            seen.add(name)

    for m in re.findall(r"capabilities in ([A-Za-z0-9\s]+)", chunk_text, re.IGNORECASE):
        name = m.strip().title()
        if name and name not in seen:
            entities.append({"name": name, "type": "Capability", "attributes": {}})
            seen.add(name)

    # ── Companies LAST (skip anything already seen) ─────────────────────
    company_pattern = r'\b([A-Z][A-Za-z0-9&]*(?:\s+[A-Z][A-Za-z0-9&]*){0,5})\b'
    for m in re.findall(company_pattern, chunk_text):
        cleaned = clean_company_name(clean_entity_name(m.strip()))  # Apply both cleaners
        if cleaned and cleaned not in seen and is_likely_company(cleaned):
            entities.append({"name": cleaned, "type": "Company", "attributes": {}})
            seen.add(cleaned)

    # ── Relations & Events ──────────────────────────────────────────────
    companies = [e["name"] for e in entities if e["type"] == "Company"]
    platforms = [e["name"] for e in entities if e["type"] == "Platform"]
    services = [e["name"] for e in entities if e["type"] == "Service"]

    if companies:
        main = companies[0]
        for p in platforms:
            relations.append({"from": main, "to": p, "relation": "operates"})
        for s in services:
            relations.append({"from": main, "to": s, "relation": "offers"})

    for f, t in re.findall(r"([A-Z][A-Za-z0-9&]*(?:\s+[A-Z][A-Za-z0-9&]*){0,4}) launched (?:its |the )?([A-Z][^.,;]+?service)", chunk_text, re.IGNORECASE):
        relations.append({"from": clean_company_name(f.strip()), "to": t.strip(), "relation": "launched"})

    # Acquisition relation extraction - cleaned names
    for f, t in re.findall(r"([A-Z][A-Za-z0-9&]*(?:\s+[A-Z][A-Za-z0-9&]*){0,4})\b acquired ([A-Z][A-Za-z0-9&]*(?:\s+[A-Z][A-Za-z0-9&]*){0,4})\b", chunk_text, re.IGNORECASE):
        from_clean = clean_company_name(clean_entity_name(f.strip()))
        to_clean = clean_company_name(clean_entity_name(t.strip()))
        if from_clean and to_clean:
            relations.append({"from": from_clean, "to": to_clean, "relation": "acquired"})

    for t in re.findall(r"partnered with ([A-Z][A-Za-z0-9\s&]+)", chunk_text, re.IGNORECASE):
        partner_name = clean_entity_name(t.strip())
        if companies and partner_name:
            relations.append({"from": companies[0], "to": partner_name, "relation": "partnered_with"})

    for t in re.findall(r"integrated with the ([^ \.,;]+)", chunk_text, re.IGNORECASE):
        if services:
            relations.append({"from": services[0], "to": t.strip(), "relation": "integrated_with"})

    # Events
    if m := re.search(r"(?:founded|incorporated) in (\d{4})", chunk_text, re.IGNORECASE):
        year = int(m.group(1))
        if companies:
            events.append({"name": f"Incorporation of {companies[0]}", "type": "Incorporation", "year": year, "company": companies[0], "tags": ["Milestone"]})

    if m := re.search(r"In (\d{4}), ([A-Z][A-Za-z0-9\s&]+) launched", chunk_text, re.IGNORECASE):
        year = int(m.group(1))
        comp = clean_company_name(m.group(2))
        if services:
            events.append({"name": f"Launch in {year}", "type": "Launch", "year": year, "company": comp, "related_to": services[0], "tags": ["Launch"]})

    # Acquisition event - only create if we can identify the acquired entity
    if m := re.search(r"acquired ([A-Z][A-Za-z0-9&]*(?:\s+[A-Z][A-Za-z0-9&]*){0,4})\b in (\d{4})", chunk_text, re.IGNORECASE):
        acquired = clean_company_name(clean_entity_name(m.group(1)))
        year = int(m.group(2))
        # Only create event if we have a clear acquirer (first company in entities)
        if companies and acquired:
            events.append({"name": f"Acquisition of {acquired} in {year}", "type": "Acquisition", "year": year, "company": companies[0], "related_to": acquired, "tags": ["Acquisition"]})

    return {"entities": entities, "relations": relations, "events": events}