import json
from pathlib import Path
from .schema import Graph
from .extractor import extract
from .graph_builder import build_graph
from .mermaid import render_mermaid
from .retrieval import retrieve_chunks


# ── Sample chunks (replace with your real prospectus chunks) ────────────
chunks = [
    {
        "chunk_id": "chunk_001",
        "page": 10,
        "text": """TechNova Inc. was founded in 2015 and is headquartered in San Francisco.
        The company operates a cloud platform called NovaCloud that offers scalable storage solutions.
        TechNova has partnered with DataFlow Systems.""",
    },
    {
        "chunk_id": "chunk_002",
        "page": 25,
        "text": """In 2020, TechNova launched its AI-powered analytics service,
        which is integrated with the NovaCloud platform.""",
    },
    {
        "chunk_id": "chunk_003",
        "page": 42,
        "text": """TechNova acquired QuantumAI in 2023, a startup specializing in quantum computing.
        This acquisition enabled new capabilities in machine learning.""",
    },
]

if __name__ == "__main__":
    main()


def main():
    """Main entry point for graph builder."""
    # Extract per chunk
    extractions = []
    for c in chunks:
        ext = extract(c["text"], c["chunk_id"], c["page"])
        extractions.append((c["chunk_id"], c["page"], ext))

    # Build normalised graph
    graph: Graph = build_graph(extractions, document_name="TechNova_Annual_Report_2024.pdf")

    # Persist to current directory
    output_dir = Path.cwd()
    
    graph_json_path = output_dir / "graph.json"
    with open(graph_json_path, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, indent=2)

    mmd = render_mermaid(graph)
    graph_mmd_path = output_dir / "graph.mmd"
    with open(graph_mmd_path, "w", encoding="utf-8") as f:
        f.write(mmd)

    print("✅ Graph JSON and Mermaid written.")
    print(f"   Nodes : {len(graph.nodes)}")
    print(f"   Edges : {len(graph.edges)}")

    # Demo retrieval (optional)
    results = retrieve_chunks("analytics service", graph, {})
    print("Relevant chunks for 'analytics service':", results)
