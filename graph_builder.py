from typing import List, Tuple, Dict, Any
from collections import defaultdict
from .schema import Node, Edge, Graph
from .utils import generate_id, CONTROLLED_RELATIONS, normalize_name, normalize_entity_label
import re


def build_graph(
    extractions: List[Tuple[str, int, Dict[str, Any]]],
    document_name: str = "document.pdf",
) -> Graph:
    """
    Rule-based extraction is intentionally lossy; the graph builder enforces
    normalization and structural correctness.
    
    Normalises entities across chunks, merges attributes/sources, builds stable IDs,
    creates event nodes with proper relationships, and attaches provenance.
    """
    label_to_node: Dict[str, Node] = {}
    normalized_to_label: Dict[str, str] = {}  # Track normalized -> canonical label mapping
    name_to_id: Dict[str, str] = {}
    edge_dict: Dict[Tuple[str, str, str], Edge] = {}
    chunk_entities: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # chunk_id -> [(type, label)]

    # Type precedence order: Platform > Service > Partner > Company
    TYPE_PRECEDENCE = {"Platform": 4, "Service": 3, "Partner": 2, "Company": 1, "Capability": 1, "Event": 0}

    # ── First pass: deduplicate by normalized label with type precedence ──
    for chunk_id, page, ext in extractions:
        for ent in ext.get("entities", []):
            name = ent["name"].strip()
            node_type = ent.get("type", "Entity")
            
            # Normalize label for deduplication (e.g., "AgroSupply Co" -> "AgroSupply")
            normalized = normalize_entity_label(name)
            
            # Track entities per chunk for integration inference
            chunk_entities[chunk_id].append((node_type, name))
            
            # Check if we've seen this normalized entity before
            if normalized in normalized_to_label:
                # Use existing canonical label
                canonical_label = normalized_to_label[normalized]
                node = label_to_node[canonical_label]
                
                # Apply type precedence
                current_precedence = TYPE_PRECEDENCE.get(node.type, 0)
                new_precedence = TYPE_PRECEDENCE.get(node_type, 0)
                
                if new_precedence > current_precedence:
                    node.type = node_type
                    # Regenerate ID with new type
                    new_id = generate_id(canonical_label, node_type)
                    node.id = new_id
                
                # Add source
                src = {"chunk_id": chunk_id, "page": page}
                if src not in node.sources:
                    node.sources.append(src)
                
                node.attributes.update(ent.get("attributes", {}))
            else:
                # New entity - use original name as canonical label
                node_id = generate_id(name, node_type)
                label_to_node[name] = Node(
                    id=node_id,
                    type=node_type,
                    label=name,
                    attributes=ent.get("attributes", {}).copy(),
                    sources=[{"chunk_id": chunk_id, "page": page}],
                )
                normalized_to_label[normalized] = name
            
            # Update name_to_id for both original and canonical
            canonical_label = normalized_to_label[normalized]
            name_to_id[name] = label_to_node[canonical_label].id
            name_to_id[canonical_label] = label_to_node[canonical_label].id

    # ── Relations with guardrails ──
    for chunk_id, page, ext in extractions:
        src_prov = {"chunk_id": chunk_id, "page": page}

        for rel in ext.get("relations", []):
            from_name = rel["from"].strip()
            to_name = rel["to"].strip()
            relation = rel.get("relation", "related_to")
            if relation not in CONTROLLED_RELATIONS:
                relation = "related_to"

            from_id = name_to_id.get(from_name)
            to_id = name_to_id.get(to_name)
            
            # Acquisition guardrail: prevent self-loops
            if from_id and to_id and from_id != to_id:
                key = (from_id, to_id, relation)
                if key not in edge_dict:
                    edge_dict[key] = Edge(from_id=from_id, to_id=to_id, relation=relation, sources=[src_prov])
                elif src_prov not in edge_dict[key].sources:
                    edge_dict[key].sources.append(src_prov)

        # Events + direct relations for Launch/Acquisition
        for ev in ext.get("events", []):
            ev_name = ev["name"]
            ev_id = f"event_{normalize_name(ev_name)}"

            if ev_id not in label_to_node:
                node = Node(
                    id=ev_id,
                    type="Event",
                    label=ev_name,
                    attributes={"year": ev.get("year"), "tags": ev.get("tags", [])},
                    sources=[src_prov],
                )
                label_to_node[ev_name] = node
            else:
                node = label_to_node[ev_name]
                if ev.get("year"):
                    node.attributes["year"] = ev.get("year")
                if src_prov not in node.sources:
                    node.sources.append(src_prov)

            # Company → Event
            comp_name = ev.get("company")
            comp_id = name_to_id.get(comp_name) if comp_name else None
            if comp_id:
                key = (comp_id, ev_id, "has_event")
                if key not in edge_dict:
                    edge_dict[key] = Edge(comp_id, ev_id, "has_event", [src_prov])
                elif src_prov not in edge_dict[key].sources:
                    edge_dict[key].sources.append(src_prov)

            # Event → related entity
            related_name = ev.get("related_to")
            related_id = name_to_id.get(related_name) if related_name else None
            if related_id:
                rel = "launched" if ev.get("type") == "Launch" else "acquired" if ev.get("type") == "Acquisition" else "related_to"
                key = (ev_id, related_id, rel)
                if key not in edge_dict:
                    edge_dict[key] = Edge(ev_id, related_id, rel, [src_prov])
                elif src_prov not in edge_dict[key].sources:
                    edge_dict[key].sources.append(src_prov)

            # DIRECT company → acquired/launch relation with guardrails
            if related_id and comp_id and comp_id != related_id:  # Prevent self-loops
                if ev.get("type") == "Acquisition":
                    key = (comp_id, related_id, "acquired")
                    if key not in edge_dict:
                        edge_dict[key] = Edge(comp_id, related_id, "acquired", [src_prov])
                    elif src_prov not in edge_dict[key].sources:
                        edge_dict[key].sources.append(src_prov)
                elif ev.get("type") == "Launch":
                    key = (comp_id, related_id, "launched")
                    if key not in edge_dict:
                        edge_dict[key] = Edge(comp_id, related_id, "launched", [src_prov])
                    elif src_prov not in edge_dict[key].sources:
                        edge_dict[key].sources.append(src_prov)

    # ── Optional safe integration inference ──
    # If Service and Platform co-occur in same chunk with integration verbs,
    # add Service → integrated_with → Platform
    for chunk_id, page, ext in extractions:
        chunk_text = ""
        # Find original chunk text from extractions context
        for cid, pg, e in extractions:
            if cid == chunk_id:
                # Get chunk text if available (we'll need to pass it or check relations)
                break
        
        # Check if chunk has both Service and Platform
        entities_in_chunk = chunk_entities.get(chunk_id, [])
        services_in_chunk = [label for typ, label in entities_in_chunk if typ == "Service"]
        platforms_in_chunk = [label for typ, label in entities_in_chunk if typ == "Platform"]
        
        # Conservative: only if we have exactly one of each and integration verbs present
        if len(services_in_chunk) == 1 and len(platforms_in_chunk) == 1:
            service_name = services_in_chunk[0]
            platform_name = platforms_in_chunk[0]
            
            service_id = name_to_id.get(service_name)
            platform_id = name_to_id.get(platform_name)
            
            # Check if integration relation already exists
            if service_id and platform_id:
                key = (service_id, platform_id, "integrated_with")
                # Only add if not already present (conservative approach)
                if key not in edge_dict:
                    # Check for integration verbs in the chunk's relations
                    has_integration_signal = any(
                        r.get("relation") == "integrated_with" 
                        for r in ext.get("relations", [])
                    )
                    
                    if has_integration_signal:
                        src_prov = {"chunk_id": chunk_id, "page": page}
                        edge_dict[key] = Edge(service_id, platform_id, "integrated_with", [src_prov])

    # ── Source nodes + described_in ─────────────────────────────────────
    for chunk_id, page, _ in extractions:
        source_id = f"source_{chunk_id}"
        if source_id not in label_to_node:
            label_to_node[source_id] = Node(
                id=source_id,
                type="Source",
                label=f"Chunk {chunk_id} (page {page})",
                attributes={"chunk_id": chunk_id, "page": page, "document": document_name},
                sources=[],
            )

    core_types = {"Company", "Platform", "Service", "Product", "Capability", "Partner", "Event"}
    for node in list(label_to_node.values()):
        if node.type in core_types:
            for src in node.sources:
                source_id = f"source_{src['chunk_id']}"
                if source_id in label_to_node:
                    key = (node.id, source_id, "described_in")
                    if key not in edge_dict:
                        edge_dict[key] = Edge(node.id, source_id, "described_in", [src])
                    elif src not in edge_dict[key].sources:
                        edge_dict[key].sources.append(src)

    return Graph(
        nodes=list(label_to_node.values()),
        edges=list(edge_dict.values()),
    )
