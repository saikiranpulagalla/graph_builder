# Streamlit Validation UI Guide

## Overview

The Streamlit app (`streamlit_app.py`) is a validation and inspection tool that sits on top of the core graph extraction pipeline. It allows you to test the system's generalization, robustness, and determinism with custom inputs.

## Purpose

This UI exists to:
- Test extraction with custom text chunks
- Compare rule-based vs LLM-based extraction
- Validate entity deduplication across chunks
- Inspect provenance tracking
- Verify deterministic graph structure
- Export results for further analysis

**Important:** This is NOT a production chatbot or Graph RAG system. It's a testing tool for the extraction pipeline.

## Installation

```bash
# Install Streamlit (only dependency)
pip install -r requirements-ui.txt

# Create .env file for LLM mode (optional)
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Running the App

```bash
# From the PARENT directory of graph_builder
streamlit run graph_builder/streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`

**Note:** The app must be run from the parent directory so it can properly import the `graph_builder` package.

## Using the Interface

### 1. Sidebar Configuration

**Extraction Mode:**
- **Rule-based Extraction**: Uses regex patterns (default, no API key needed)
- **LLM-based Extraction**: Uses OpenAI GPT (requires `OPENAI_API_KEY` environment variable)

**Input Chunks:**
- Enter 1-3 text chunks in the text areas
- Each chunk represents a document section
- Chunks can reference the same entities (tests deduplication)

**Generate Button:**
- Click to run the extraction pipeline
- Results appear in the main area tabs

### 2. Main Area Tabs

**Graph JSON Tab:**
- Shows complete graph structure
- Includes nodes, edges, and provenance
- Download button for `graph.json`

**Mermaid Diagram Tab:**
- Shows Mermaid visualization code
- Copy and paste into [Mermaid Live Editor](https://mermaid.live)
- Download button for `graph.mmd`

**Stats Tab:**
- Node and edge counts
- Node type distribution
- Validation checklist:
  - Entity deduplication working
  - Provenance tracking present
  - All nodes have types
  - Relationships extracted

## Example Test Cases

### Test 1: Entity Deduplication

**Chunk 1:**
```
TechNova Inc. operates a cloud platform called NovaCloud.
```

**Chunk 2:**
```
TechNova has partnered with DataFlow Systems.
```

**Expected Result:**
- Single "TechNova" node (deduplicated)
- Two source references on the TechNova node

### Test 2: Type Classification

**Chunk 1:**
```
CloudCorp launched its AI-powered analytics service in 2020.
```

**Expected Result:**
- "AI-powered analytics service" classified as Service (not Company)
- "CloudCorp" classified as Company
- Launch event node created

### Test 3: Cross-Chunk Relations

**Chunk 1:**
```
DataPlatform is a cloud platform operated by DataCorp.
```

**Chunk 2:**
```
DataCorp's analytics service is integrated with DataPlatform.
```

**Expected Result:**
- "DataPlatform" correctly typed as Platform
- "analytics service" correctly typed as Service
- Relationship: Service → integrated_with → Platform

## LLM Mode Setup

To use LLM-based extraction with Google Gemini:

```bash
# Install dependencies
pip install -r requirements-ui.txt

# Create .env file
cp .env.example .env

# Edit .env and add your Google Gemini API key:
# GEMINI_API_KEY=your-key-here
# GEMINI_MODEL=gemini-2.0-flash-exp

# Run the app
streamlit run graph_builder/streamlit_app.py
```

**Get your API key:** https://makersuite.google.com/app/apikey

**Note:** 
- LLM mode uses Google Gemini with a structured prompt
- Default model: gemini-2.0-flash-exp (configurable via GEMINI_MODEL in .env)
- Other options: gemini-1.5-flash, gemini-1.5-pro
- If no API key is set in .env, the app shows a stub example
- It's a minimal implementation for comparison purposes

## Architecture

```
User Input (Streamlit UI)
    ↓
extract() [rule-based OR llm-based]
    ↓
build_graph() [existing pipeline]
    ↓
render_mermaid() [existing pipeline]
    ↓
Display Results (JSON, Mermaid, Stats)
```

The UI calls the existing pipeline functions without modifying core logic.

## Validation Checklist

Use the Stats tab to verify:

1. **Entity Deduplication**: Same entity mentioned in multiple chunks → single node
2. **Provenance Tracking**: Every node has `sources` array with chunk references
3. **Type Classification**: Entities correctly classified (Platform, Service, etc.)
4. **Relationship Extraction**: Edges created with correct relation types
5. **Deterministic Output**: Same input → same graph structure

## Troubleshooting

**Issue: "LLM extraction failed"**
- Check that `.env` file exists in the graph_builder directory
- Verify `GEMINI_API_KEY` is set in `.env` file
- Verify API key is valid (get from https://makersuite.google.com/app/apikey)
- Falls back to stub data if LLM unavailable

**Issue: "No nodes extracted"**
- Check that text chunks contain recognizable entities
- Try rule-based mode first (more predictable)
- Verify text is not empty

**Issue: Mermaid diagram not rendering**
- Copy the code from the Mermaid tab
- Paste into [Mermaid Live Editor](https://mermaid.live)
- The app shows code only (not rendered diagram)

## Limitations

This UI is intentionally minimal:
- No vector database integration
- No graph traversal queries
- No persistent storage
- No multi-document processing
- No entity resolution beyond exact label matching

For production Graph RAG, extend the core pipeline (not the UI).

## Next Steps

After validating with the UI:
1. Use `run.py` for batch processing
2. Integrate the pipeline into your application
3. Add vector search for retrieval
4. Implement graph traversal for multi-hop queries
5. Connect to persistent storage (Neo4j, PostgreSQL, etc.)

---

**Remember:** The Streamlit app is a testing tool. The core deliverable is the graph extraction pipeline itself.
