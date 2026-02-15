"""
This Streamlit app is a validation and inspection layer only.
The core deliverable is the graph extraction pipeline.
The UI exists to test generalization, robustness, and determinism.
"""

import streamlit as st
import json
from typing import Dict, Any, List, Tuple
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure we can import from graph_builder package
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# Add both current and parent directory to path for flexibility
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import - handle both local and Streamlit Cloud paths
try:
    from graph_builder.extractor import extract as rule_based_extract
    from graph_builder.graph_builder import build_graph, normalize_llm_graph
    from graph_builder.mermaid import render_mermaid
except ImportError:
    # If running from graph_builder directory directly
    from extractor import extract as rule_based_extract
    from graph_builder import build_graph, normalize_llm_graph
    from mermaid import render_mermaid


# ============================================================================
# MERMAID RENDERING UTILITY
# ============================================================================

def render_mermaid_html(mermaid_code: str) -> None:
    """
    Render Mermaid diagram visually using st.components.html.
    
    Args:
        mermaid_code: Mermaid diagram code to render
    """
    import streamlit.components.v1 as components
    
    # HTML template with Mermaid CDN and rendering
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background-color: white;
                overflow: auto;
            }}
            .mermaid {{
                display: flex;
                justify-content: center;
                align-items: center;
            }}
        </style>
    </head>
    <body>
        <div class="mermaid">
{mermaid_code}
        </div>
    </body>
    </html>
    """
    
    # Render with fixed height and scrolling enabled
    components.html(html_template, height=600, scrolling=True)


# ============================================================================
# LLM-BASED EXTRACTION (GOOGLE GEMINI)
# ============================================================================

def llm_extract(chunk_text: str, chunk_id: str, page: int) -> Dict[str, Any]:
    """
    LLM-based extraction using Google Gemini.
    Returns the same structured format as rule-based extraction.
    """
    # Check for API key - try Streamlit secrets first, then environment variables
    api_key = None
    model_name = "gemini-2.0-flash-exp"
    
    # Try Streamlit secrets (for Streamlit Cloud)
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        model_name = st.secrets.get("GEMINI_MODEL", "gemini-2.0-flash-exp")
    except (AttributeError, FileNotFoundError):
        # Fall back to environment variables (for local development)
        api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    
    if not api_key:
        # Return stub data if no API key
        st.info("💡 LLM mode requires GEMINI_API_KEY. Add it in Streamlit Cloud Secrets or .env file. Using stub data for demo.")
        return {
            "entities": [
                {"name": "Example Corp", "type": "Company", "attributes": {}},
                {"name": "Example Platform", "type": "Platform", "attributes": {}}
            ],
            "relations": [
                {"from": "Example Corp", "to": "Example Platform", "relation": "operates"}
            ],
            "events": []
        }
    
    # Google Gemini implementation with strict ontology
    try:
        import google.generativeai as genai
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""Extract entities, relations, and events from the text following STRICT rules.

CRITICAL CONSTRAINTS:

1. ALLOWED ENTITY TYPES ONLY (no exceptions):
   - Company: Business organizations (e.g., TechCorp, DataSystems)
   - Platform: Technology platforms (e.g., CloudBase, NovaCloud)
   - Service: Products/services offered (e.g., analytics service, storage service)
   - Partner: Business partners (e.g., partner companies)
   - Capability: Technical or organizational capabilities (e.g., Machine Learning, Data Processing)
   - Event: Temporal milestones (e.g., Launch, Acquisition, Incorporation)

2. DO NOT CREATE ENTITIES FOR:
   - People, users, roles, actors (e.g., farmers, distributors, customers, users)
   - Beneficiaries or user groups
   - Generic concepts that aren't technical capabilities

3. ALLOWED RELATIONS ONLY (use exact strings):
   - operates: Company operates Platform
   - offers: Company offers Service
   - launched: Company/Event launched Service
   - acquired: Company/Event acquired Company
   - partnered_with: Company partnered with Partner
   - integrated_with: Service integrated with Platform
   - has_event: Company has Event
   - described_in: Entity described in Source

4. DO NOT CREATE RELATIONS:
   - To people, users, or actors
   - Using verbs like "serves", "helps", "benefits", "targets"
   - Between entities and non-entities

5. EVENT MODELING:
   - Events must have: name, type (Launch/Acquisition/Milestone), year, tags
   - Events must connect: Company → has_event → Event
   - Events must link to entities: Event → launched/acquired → Entity
   - Event tags must be semantic: ["Launch"], ["Acquisition"], ["Milestone"]

6. IF AMBIGUOUS: OMIT IT
   - Prefer omission over guessing
   - Only extract what is explicitly stated
   - Structural correctness > semantic richness

Return ONLY valid JSON (no markdown, no code blocks, no explanations):
{{
  "entities": [
    {{"name": "EntityName", "type": "Company|Platform|Service|Partner|Capability", "attributes": {{}}}}
  ],
  "relations": [
    {{"from": "EntityName1", "to": "EntityName2", "relation": "operates|offers|launched|acquired|partnered_with|integrated_with"}}
  ],
  "events": [
    {{"name": "Event description", "type": "Launch|Acquisition|Milestone", "year": 2023, "company": "CompanyName", "related_to": "EntityName", "tags": ["Launch"]}}
  ]
}}

Text to analyze:
{chunk_text}

JSON output:"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            # Remove first line (```json or ```)
            lines = result_text.split('\n')
            result_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else result_text
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        
        result = json.loads(result_text)
        
        # Post-processing validation: filter out invalid entity types
        valid_types = {"Company", "Platform", "Service", "Partner", "Capability", "Event"}
        if "entities" in result:
            result["entities"] = [
                e for e in result["entities"] 
                if e.get("type") in valid_types
            ]
        
        # Validate relations use only allowed verbs
        valid_relations = {
            "operates", "offers", "launched", "acquired", 
            "partnered_with", "integrated_with", "has_event", "described_in"
        }
        if "relations" in result:
            result["relations"] = [
                r for r in result["relations"]
                if r.get("relation") in valid_relations
            ]
        
        # Validate events have required fields
        if "events" in result:
            validated_events = []
            for ev in result["events"]:
                if ev.get("name") and ev.get("type") in {"Launch", "Acquisition", "Milestone"}:
                    validated_events.append(ev)
            result["events"] = validated_events
        
        return result
        
    except ImportError:
        st.warning("⚠️ google-generativeai package not installed. Install with: pip install google-generativeai")
        return {"entities": [], "relations": [], "events": []}
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Failed to parse LLM response as JSON: {e}")
        return {"entities": [], "relations": [], "events": []}
    except Exception as e:
        st.warning(f"⚠️ LLM extraction failed: {e}. Using empty result.")
        return {"entities": [], "relations": [], "events": []}


# ============================================================================
# EXTRACTION MODE DISPATCHER
# ============================================================================

def extract_with_mode(mode: str, chunk_text: str, chunk_id: str, page: int) -> Dict[str, Any]:
    """
    Dispatch to rule-based or LLM-based extraction based on mode.
    Ensures interface compatibility.
    """
    if mode == "Rule-based Extraction":
        return rule_based_extract(chunk_text, chunk_id, page)
    else:  # LLM-based Extraction
        return llm_extract(chunk_text, chunk_id, page)


# ============================================================================
# GRAPH GENERATION PIPELINE
# ============================================================================

def generate_graph(chunks: List[Dict[str, str]], mode: str) -> Tuple[Dict, str, Dict]:
    """
    Run the complete pipeline: extract → build_graph → render_mermaid
    
    Args:
        chunks: List of {chunk_id, page, text}
        mode: "Rule-based Extraction" or "LLM-based Extraction"
    
    Returns:
        (graph_dict, mermaid_text, stats)
    """
    # Step 1: Extract from all chunks
    extractions = []
    for chunk in chunks:
        if chunk["text"].strip():
            ext = extract_with_mode(mode, chunk["text"], chunk["chunk_id"], chunk["page"])
            extractions.append((chunk["chunk_id"], chunk["page"], ext))
    
    if not extractions:
        return {}, "", {"nodes": 0, "edges": 0}
    
    # Step 2: Build normalized graph
    graph = build_graph(extractions, document_name="streamlit_input.txt")
    
    # Step 2.5: Apply LLM-specific normalization if using LLM mode
    if mode == "LLM-based Extraction":
        graph = normalize_llm_graph(graph)
    
    # Step 3: Render Mermaid
    mermaid_text = render_mermaid(graph)
    
    # Step 4: Convert to dict and compute stats
    graph_dict = graph.to_dict()
    stats = {
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "node_types": {node.type: sum(1 for n in graph.nodes if n.type == node.type) 
                       for node in graph.nodes}
    }
    
    return graph_dict, mermaid_text, stats


# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(
        page_title="Graph Builder Validator",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Knowledge Graph Extraction Validator")
    st.markdown("**Validation and inspection tool for the graph extraction pipeline**")
    
    # ── SIDEBAR: Configuration ──────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Extraction mode selector
        mode = st.radio(
            "Extraction Mode",
            ["Rule-based Extraction", "LLM-based Extraction"],
            help="Rule-based uses regex patterns. LLM-based uses Google Gemini (requires GEMINI_API_KEY in Streamlit Secrets or .env file)."
        )
        
        st.divider()
        st.header("📝 Input Chunks")
        st.caption("Enter up to 3 text chunks to test extraction")
        
        # Three text input areas
        chunk1 = st.text_area(
            "Chunk 1",
            height=120,
            placeholder="Enter first text chunk...",
            key="chunk1"
        )
        
        chunk2 = st.text_area(
            "Chunk 2",
            height=120,
            placeholder="Enter second text chunk (optional)...",
            key="chunk2"
        )
        
        chunk3 = st.text_area(
            "Chunk 3",
            height=120,
            placeholder="Enter third text chunk (optional)...",
            key="chunk3"
        )
        
        st.divider()
        
        # Generate button
        generate_btn = st.button("🚀 Generate Graph", type="primary", use_container_width=True)
    
    # ── MAIN AREA: Results ──────────────────────────────────────────────
    
    # Show instructions if no generation yet
    if not generate_btn and "graph_data" not in st.session_state:
        st.info("👈 Enter text chunks in the sidebar and click 'Generate Graph' to begin")
        
        with st.expander("ℹ️ How to use this tool"):
            st.markdown("""
            **Purpose**: Test whether the graph extraction pipeline generalizes across different inputs.
            
            **Steps**:
            1. Choose extraction mode (Rule-based or LLM-based)
            2. Paste 1-3 text chunks containing entities and relationships
            3. Click "Generate Graph"
            4. Inspect the results in the tabs below
            
            **What to look for**:
            - Entity deduplication across chunks
            - Correct entity type classification
            - Provenance tracking (source chunks)
            - Deterministic structure
            - Semantic relationship extraction
            """)
        return
    
    # ── GENERATE GRAPH ──────────────────────────────────────────────────
    if generate_btn:
        # Collect non-empty chunks
        chunks = []
        for i, text in enumerate([chunk1, chunk2, chunk3], 1):
            if text.strip():
                chunks.append({
                    "chunk_id": f"chunk_{i:03d}",
                    "page": i * 10,  # Mock page numbers
                    "text": text
                })
        
        # Validate input
        if not chunks:
            st.warning("⚠️ Please enter at least one text chunk")
            return
        
        # Generate graph
        with st.spinner("Extracting entities and building graph..."):
            try:
                graph_dict, mermaid_text, stats = generate_graph(chunks, mode)
                
                # Store in session state
                st.session_state.graph_data = graph_dict
                st.session_state.mermaid_text = mermaid_text
                st.session_state.stats = stats
                st.session_state.mode = mode
                
                st.success(f"✅ Graph generated successfully using {mode}")
                
            except Exception as e:
                st.error(f"❌ Error generating graph: {e}")
                return
    
    # ── DISPLAY RESULTS ─────────────────────────────────────────────────
    if "graph_data" in st.session_state:
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Graph JSON", "🎨 Mermaid Diagram", "📈 Stats"])
        
        # Tab 1: Graph JSON
        with tab1:
            st.subheader("Graph JSON Output")
            st.caption("Complete graph structure with nodes, edges, and provenance")
            
            # Pretty-print JSON
            json_str = json.dumps(st.session_state.graph_data, indent=2)
            st.code(json_str, language="json", line_numbers=True)
            
            # Download button
            st.download_button(
                label="📥 Download graph.json",
                data=json_str,
                file_name="graph.json",
                mime="application/json"
            )
        
        # Tab 2: Mermaid Diagram
        with tab2:
            st.subheader("Mermaid Diagram")
            st.caption("Visual representation of the knowledge graph")
            
            # Display Mermaid code
            st.code(st.session_state.mermaid_text, language="mermaid")
            
            # Download button
            st.download_button(
                label="📥 Download graph.mmd",
                data=st.session_state.mermaid_text,
                file_name="graph.mmd",
                mime="text/plain"
            )
            
            st.divider()
            
            # Render visual diagram
            st.subheader("Visual Rendering")
            st.caption("Interactive Mermaid diagram rendered below")
            
            try:
                render_mermaid_html(st.session_state.mermaid_text)
            except Exception as e:
                st.warning(f"⚠️ Could not render diagram: {e}")
                st.info("💡 Copy the code above and paste into [Mermaid Live Editor](https://mermaid.live) to visualize")
        
        # Tab 3: Stats
        with tab3:
            st.subheader("Graph Statistics")
            st.caption(f"Extraction mode: {st.session_state.mode}")
            
            # Display metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Nodes", st.session_state.stats["nodes"])
            with col2:
                st.metric("Total Edges", st.session_state.stats["edges"])
            
            st.divider()
            
            # Node type breakdown
            st.subheader("Node Type Distribution")
            node_types = st.session_state.stats.get("node_types", {})
            
            if node_types:
                for node_type, count in sorted(node_types.items(), key=lambda x: -x[1]):
                    st.metric(node_type, count)
            else:
                st.info("No nodes extracted")
            
            st.divider()
            
            # Validation checklist
            st.subheader("✅ Validation Checklist")
            
            graph_data = st.session_state.graph_data
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            
            # Check deduplication
            labels = [n["label"] for n in nodes]
            has_duplicates = len(labels) != len(set(labels))
            st.checkbox("Entity deduplication working", value=not has_duplicates, disabled=True)
            
            # Check provenance
            has_provenance = all(n.get("sources") for n in nodes if n["type"] != "Source")
            st.checkbox("Provenance tracking present", value=has_provenance, disabled=True)
            
            # Check type classification
            has_types = all(n.get("type") for n in nodes)
            st.checkbox("All nodes have types", value=has_types, disabled=True)
            
            # Check edges
            has_edges = len(edges) > 0
            st.checkbox("Relationships extracted", value=has_edges, disabled=True)


if __name__ == "__main__":
    main()
