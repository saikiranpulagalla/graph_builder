from typing import List, Tuple, Dict, Any
from collections import defaultdict
from .schema import Node, Edge, Graph
from .utils import (
    generate_id, CONTROLLED_RELATIONS, normalize_name, normalize_entity_label,
    normalize_for_comparison, is_alias, is_invalid_entity_name, choose_best_label
)
import re


def normalize_llm_graph(graph: Graph) -> Graph:
    """
    Apply LLM-specific normalization fixes.
    
    1. Service name deduplication (merge similar service names)
    2. Partner vs Company normalization (reclassify based on relations)
    3. Event-first enforcement (remove duplicate direct relationships)
    
    This runs AFTER LLM extraction and BEFORE rendering.
    """
    nodes = list(graph.nodes)
    edges = list(graph.edges)
    
    # ── FIX 1: SERVICE NAME DEDUPLICATION ──────────────────────────────
    # Merge similar Service nodes (e.g., "monitoring service" vs "real-time monitoring service")
    service_nodes = [n for n in nodes if n.type == "Service"]
    service_map = {}  # old_id -> new_id
    merged_services = []
    processed_services = set()
    
    for i, service in enumerate(service_nodes):
        if service.id in processed_services:
            continue
        
        # Find similar services
        similar = [service]
        for j, other in enumerate(service_nodes[i+1:], start=i+1):
            if other.id in processed_services:
                continue
            if is_alias(service.label, other.label):
                similar.append(other)
                processed_services.add(other.id)
        
        # Merge if multiple similar services found
        if len(similar) > 1:
            # Choose most descriptive label
            best_label = choose_best_label([s.label for s in similar])
            
            # Merge sources
            all_sources = []
            for s in similar:
                all_sources.extend(s.sources)
            
            # Deduplicate sources
            unique_sources = []
            seen = set()
            for src in all_sources:
                key = (src.get("chunk_id"), src.get("page"))
                if key not in seen:
                    unique_sources.append(src)
                    seen.add(key)
            
            # Create merged service
            merged = Node(
                id=generate_id(best_label, "Service"),
                type="Service",
                label=best_label,
                attributes=similar[0].attributes.copy(),
                sources=unique_sources
            )
            
            # Map all old IDs to new ID
            for s in similar:
                service_map[s.id] = merged.id
            
            merged_services.append(merged)
            processed_services.add(service.id)
        else:
            merged_services.append(service)
            service_map[service.id] = service.id
            processed_services.add(service.id)
    
    # Update nodes list with merged services
    non_service_nodes = [n for n in nodes if n.type != "Service"]
    nodes = non_service_nodes + merged_services
    
    # Update edges to point to merged services
    updated_edges = []
    for edge in edges:
        new_from = service_map.get(edge.from_id, edge.from_id)
        new_to = service_map.get(edge.to_id, edge.to_id)
        
        # Skip self-loops
        if new_from == new_to:
            continue
        
        updated_edges.append(Edge(
            from_id=new_from,
            to_id=new_to,
            relation=edge.relation,
            sources=edge.sources
        ))
    
    edges = updated_edges
    
    # ── FIX 2: PARTNER VS COMPANY NORMALIZATION ────────────────────────
    # Reclassify entities that only participate in partnered_with relations as Partner
    
    # Build relation map: entity_id -> set of relation types
    entity_relations = {}
    for edge in edges:
        if edge.from_id not in entity_relations:
            entity_relations[edge.from_id] = set()
        entity_relations[edge.from_id].add(edge.relation)
    
    # Reclassify Company nodes that only have partnered_with relations
    reclassified_nodes = []
    node_type_map = {}  # old_id -> new_id (if type changed)
    
    for node in nodes:
        if node.type == "Company":
            relations = entity_relations.get(node.id, set())
            # Remove non-business relations
            business_relations = relations - {"described_in", "has_event"}
            
            # If only partnered_with relation exists, reclassify as Partner
            if business_relations == {"partnered_with"}:
                new_node = Node(
                    id=generate_id(node.label, "Partner"),
                    type="Partner",
                    label=node.label,
                    attributes=node.attributes.copy(),
                    sources=node.sources.copy()
                )
                reclassified_nodes.append(new_node)
                node_type_map[node.id] = new_node.id
            else:
                reclassified_nodes.append(node)
                node_type_map[node.id] = node.id
        else:
            reclassified_nodes.append(node)
            if node.id not in node_type_map:
                node_type_map[node.id] = node.id
    
    nodes = reclassified_nodes
    
    # Update edges with reclassified node IDs
    updated_edges = []
    for edge in edges:
        new_from = node_type_map.get(edge.from_id, edge.from_id)
        new_to = node_type_map.get(edge.to_id, edge.to_id)
        
        # Skip if nodes don't exist
        if new_from not in node_type_map.values() or new_to not in node_type_map.values():
            continue
        
        # Skip self-loops
        if new_from == new_to:
            continue
        
        updated_edges.append(Edge(
            from_id=new_from,
            to_id=new_to,
            relation=edge.relation,
            sources=edge.sources
        ))
    
    edges = updated_edges
    
    # ── FIX 3: EVENT-FIRST ENFORCEMENT ─────────────────────────────────
    # Remove duplicate direct relationships when Event exists
    
    event_nodes = {n.id for n in nodes if n.type == "Event"}
    
    # Find event-mediated relationships
    event_mediated = set()
    for edge in edges:
        if edge.from_id in event_nodes and edge.relation in {"launched", "acquired"}:
            # This is Event -> launched/acquired -> Target
            # Find Company -> has_event -> Event
            for e2 in edges:
                if e2.to_id == edge.from_id and e2.relation == "has_event":
                    # Found: Company -> has_event -> Event -> launched/acquired -> Target
                    # Mark direct Company -> launched/acquired -> Target as redundant
                    event_mediated.add((e2.from_id, edge.to_id, edge.relation))
    
    # Remove redundant direct edges
    final_edges = []
    for edge in edges:
        if (edge.from_id, edge.to_id, edge.relation) in event_mediated:
            continue  # Skip redundant edge
        final_edges.append(edge)
    
    # ── DEDUPLICATE EDGES ──────────────────────────────────────────────
    edge_dict = {}
    for edge in final_edges:
        key = (edge.from_id, edge.to_id, edge.relation)
        if key not in edge_dict:
            edge_dict[key] = edge
        else:
            # Merge sources
            existing = edge_dict[key]
            for src in edge.sources:
                if src not in existing.sources:
                    existing.sources.append(src)
    
    # ── SORT FOR DETERMINISTIC OUTPUT ──────────────────────────────────
    sorted_nodes = sorted(nodes, key=lambda n: (n.type, n.label, n.id))
    sorted_edges = sorted(edge_dict.values(), key=lambda e: (e.from_id, e.relation, e.to_id))
    
    return Graph(nodes=sorted_nodes, edges=sorted_edges)


def normalize_graph(graph: Graph) -> Graph:
    """
    Normalize graph to ensure correctness and consistency.
    
    1. Remove invalid entities (verbs, fragments)
    2. Merge aliases (e.g., "Nimbus" + "Nimbus Solutions")
    3. Enforce event-first modeling (remove redundant direct edges)
    4. Remove unsupported relations
    5. Deduplicate semantically equivalent services
    6. Sort for deterministic output
    """
    # Step 1: Filter out invalid entities
    valid_nodes = []
    for node in graph.nodes:
        if node.type == "Source":
            valid_nodes.append(node)
            continue
        
        if is_invalid_entity_name(node.label):
            continue  # Skip invalid entities
        
        valid_nodes.append(node)
    
    # Step 2: Merge aliases
    merged_nodes = []
    node_map = {}  # old_id -> new_id
    processed = set()
    
    for i, node in enumerate(valid_nodes):
        if node.id in processed:
            continue
        
        # Find all aliases of this node
        aliases = [node]
        for j, other in enumerate(valid_nodes[i+1:], start=i+1):
            if other.id in processed:
                continue
            if other.type == node.type and is_alias(node.label, other.label):
                aliases.append(other)
                processed.add(other.id)
        
        # Merge aliases into one node
        if len(aliases) > 1:
            # Choose best label
            all_labels = [n.label for n in aliases]
            best_label = choose_best_label(all_labels)
            
            # Merge sources
            all_sources = []
            for alias in aliases:
                all_sources.extend(alias.sources)
            
            # Remove duplicate sources
            unique_sources = []
            seen_sources = set()
            for src in all_sources:
                src_key = (src.get("chunk_id"), src.get("page"))
                if src_key not in seen_sources:
                    unique_sources.append(src)
                    seen_sources.add(src_key)
            
            # Create merged node
            merged_node = Node(
                id=generate_id(best_label, node.type),
                type=node.type,
                label=best_label,
                attributes=node.attributes.copy(),
                sources=unique_sources
            )
            
            # Map all old IDs to new ID
            for alias in aliases:
                node_map[alias.id] = merged_node.id
            
            merged_nodes.append(merged_node)
            processed.add(node.id)
        else:
            merged_nodes.append(node)
            node_map[node.id] = node.id
            processed.add(node.id)
    
    # Step 3: Update edges with new node IDs
    updated_edges = []
    for edge in graph.edges:
        new_from = node_map.get(edge.from_id, edge.from_id)
        new_to = node_map.get(edge.to_id, edge.to_id)
        
        # Skip if nodes were removed
        if new_from not in node_map.values() or new_to not in node_map.values():
            continue
        
        # Skip self-loops
        if new_from == new_to:
            continue
        
        # Filter out unsupported relations
        if edge.relation not in CONTROLLED_RELATIONS:
            continue
        
        updated_edges.append(Edge(
            from_id=new_from,
            to_id=new_to,
            relation=edge.relation,
            sources=edge.sources
        ))
    
    # Step 4: Enforce event-first modeling
    # Find all events
    event_nodes = {n.id for n in merged_nodes if n.type == "Event"}
    
    # Find event-mediated relationships
    event_mediated = set()
    for edge in updated_edges:
        if edge.from_id in event_nodes and edge.relation in {"launched", "acquired"}:
            # This is Event -> launched/acquired -> Target
            # Find Company -> has_event -> Event
            for e2 in updated_edges:
                if e2.to_id == edge.from_id and e2.relation == "has_event":
                    # Found: Company -> has_event -> Event -> launched/acquired -> Target
                    # Mark the direct Company -> launched/acquired -> Target as redundant
                    event_mediated.add((e2.from_id, edge.to_id, edge.relation))
    
    # Remove redundant direct edges
    final_edges = []
    for edge in updated_edges:
        if (edge.from_id, edge.to_id, edge.relation) in event_mediated:
            continue  # Skip redundant edge
        final_edges.append(edge)
    
    # Step 5: Deduplicate edges
    edge_dict = {}
    for edge in final_edges:
        key = (edge.from_id, edge.to_id, edge.relation)
        if key not in edge_dict:
            edge_dict[key] = edge
        else:
            # Merge sources
            existing = edge_dict[key]
            for src in edge.sources:
                if src not in existing.sources:
                    existing.sources.append(src)
    
    # Step 6: Sort for deterministic output
    sorted_nodes = sorted(merged_nodes, key=lambda n: (n.type, n.label, n.id))
    sorted_edges = sorted(edge_dict.values(), key=lambda e: (e.from_id, e.relation, e.to_id))
    
    return Graph(nodes=sorted_nodes, edges=sorted_edges)


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

    raw_graph = Graph(
        nodes=list(label_to_node.values()),
        edges=list(edge_dict.values()),
    )
    
    # Apply normalization to ensure correctness and consistency
    return normalize_graph(raw_graph)

