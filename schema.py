from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class Node:
    """Core node in the knowledge graph."""
    id: str
    type: str
    label: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Edge:
    """Directed edge with provenance."""
    from_id: str
    to_id: str
    relation: str
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Graph:
    """Complete graph container."""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }
