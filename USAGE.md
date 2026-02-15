# Quick Usage Guide

## Running the System

### Option 1: From inside graph_builder folder (Recommended)
```bash
cd graph_builder
python run.py
```

### Option 2: From parent directory
```bash
python -m graph_builder
```

## Output

Both commands generate two files in the **current directory**:

1. **graph.json** - Complete knowledge graph in JSON format
2. **graph.mmd** - Mermaid diagram for visualization

## Viewing the Graph

1. Open [Mermaid Live Editor](https://mermaid.live)
2. Copy the contents of `graph.mmd`
3. Paste into the editor
4. View your interactive graph!

## Customizing the Data

Edit `__main__.py` and modify the `chunks` list:

```python
chunks = [
    {
        "chunk_id": "your_chunk_id",
        "page": 1,
        "text": "Your document text here...",
    },
    # Add more chunks...
]
```

Then run again:
```bash
python run.py
```

## Understanding the Output

### graph.json Structure
```json
{
  "nodes": [
    {
      "id": "platform_novacloud",
      "type": "Platform",
      "label": "NovaCloud",
      "attributes": {},
      "sources": [
        {"chunk_id": "chunk_001", "page": 10}
      ]
    }
  ],
  "edges": [
    {
      "from_id": "company_technova",
      "to_id": "platform_novacloud",
      "relation": "operates",
      "sources": [
        {"chunk_id": "chunk_001", "page": 10}
      ]
    }
  ]
}
```

### Entity Types Recognized

- **Company** - Business entities (TechNova, QuantumAI)
- **Platform** - Technology platforms (NovaCloud)
- **Service** - Products/services (AI-powered analytics)
- **Partner** - Business partners (DataFlow Systems)
- **Capability** - Technical capabilities (Machine Learning)
- **Event** - Temporal events (Acquisitions, Launches)
- **Source** - Document provenance (Chunk references)

### Relationship Types

- `operates` - Company operates Platform
- `offers` - Company offers Service
- `partnered_with` - Company partnered with Partner
- `integrated_with` - Service integrated with Platform
- `acquired` - Company acquired Company
- `launched` - Company/Event launched Service
- `has_event` - Company has Event
- `described_in` - Entity described in Source

## Common Tasks

### Add a New Entity Type

1. Edit `extractor.py` - Add extraction pattern
2. Edit `mermaid.py` - Add to groups and class_map
3. Edit `utils.py` - Add to CONTROLLED_RELATIONS if needed

### Change Visualization Colors

Edit `mermaid.py` and modify the `classDef` section:

```python
classDef company fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
```

### Query the Graph

Use the retrieval function:

```python
from graph_builder.retrieval import retrieve_chunks

relevant_chunks = retrieve_chunks("your query", graph, chunk_map)
print(relevant_chunks)
```

## Troubleshooting

### "No module named graph_builder"
- Make sure you're running from the correct directory
- Use `python run.py` from inside graph_builder folder

### "Files not generated"
- Check for errors in the console output
- Verify you have write permissions in the current directory

### "Entity misclassified"
- Check extraction patterns in `extractor.py`
- Specific patterns (Platform, Service) run before generic (Company)

### "Mermaid diagram looks wrong"
- Verify the graph.json has correct types
- Check that class_map in mermaid.py includes all types

## Next Steps

1. Replace sample chunks with your real data
2. Customize extraction patterns for your domain
3. Add new entity types as needed
4. Integrate with your LLM/NER pipeline
5. Set up persistent storage (Neo4j, PostgreSQL)

For detailed documentation, see [README.md](README.md)
