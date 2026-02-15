from typing import List, Dict
from .schema import Graph


def retrieve_chunks(query: str, graph: Graph, chunk_map: Dict[str, str]) -> List[str]:
    """
    Simple entity/relation based retrieval for Graph RAG.
    In production: replace with vector search over chunk embeddings + graph traversal.
    """
    query_lower = query.lower()
    relevant_chunk_ids = set()

    for node in graph.nodes:
        if (query_lower in node.label.lower() or
            any(query_lower in str(v).lower() for v in node.attributes.values())):
            for src in node.sources:
                relevant_chunk_ids.add(src["chunk_id"])

    # Also check edge relations (optional)
    for edge in graph.edges:
        if query_lower in edge.relation.lower():
            # add sources from both endpoints
            for node in graph.nodes:
                if node.id in (edge.from_id, edge.to_id):
                    for src in node.sources:
                        relevant_chunk_ids.add(src["chunk_id"])

    return sorted(list(relevant_chunk_ids))
