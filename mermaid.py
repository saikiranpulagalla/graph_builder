# graph_builder/mermaid.py
from .schema import Graph


def render_mermaid(graph: Graph) -> str:
    """Clean, grouped, professionally styled Mermaid — generated ONLY from Graph JSON."""
    lines = ["graph TD"]

    # Group nodes by type
    groups: dict[str, list] = {
        "Company": [], "Platform": [], "Service": [], "Partner": [],
        "Capability": [], "Event": [], "Source": []
    }
    for node in graph.nodes:
        if node.type in groups:
            groups[node.type].append(node)

    # Subgraphs in logical reading order
    for title, key in [
        ("Companies", "Company"),
        ("Platforms", "Platform"),
        ("Services", "Service"),
        ("Partners", "Partner"),
        ("Capabilities", "Capability"),
        ("Events", "Event"),
        ("Sources", "Source"),
    ]:
        nodes = sorted(groups[key], key=lambda n: n.label)
        if not nodes:
            continue
        lines.append(f"    subgraph {title}")
        for node in nodes:
            attrs = [f"{k}: {v}" for k, v in node.attributes.items() if v]
            label = node.label
            if attrs:
                label += "<br/>" + "<br/>".join(attrs)
            lines.append(f'        {node.id}["{label}"]')
        lines.append("    end")

    # Edges
    lines.append("")
    for edge in sorted(graph.edges, key=lambda e: (e.from_id, e.relation)):
        lines.append(f"    {edge.from_id} -->|{edge.relation}| {edge.to_id}")

    # Dynamic styling (no hard-coding)
    lines.append("\n    %% === STYLING ===")
    class_map = {
        "Company": "company",
        "Platform": "platform",
        "Service": "service",
        "Partner": "partner",
        "Capability": "capability",
        "Event": "event",
        "Source": "source",
    }
    for typ, cls in class_map.items():
        node_ids = [n.id for n in groups[typ]]
        if node_ids:
            lines.append(f'    class {",".join(node_ids)} {cls}')

    lines.append("""
    classDef company    fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef platform   fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef service    fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    classDef partner    fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef capability fill:#f1f8e9,stroke:#689f38,stroke-width:2px
    classDef event      fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    classDef source     fill:#f5f5f5,stroke:#616161,stroke-width:1px
    """)

    return "\n".join(lines)