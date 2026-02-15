# Graph Ontology - Strict Constraints

## Overview

This document defines the strict ontology constraints for the knowledge graph extraction system. These rules ensure structural correctness and consistency across both rule-based and LLM-based extraction.

## Design Philosophy

**Structural Correctness > Semantic Richness**

- Prefer omission over guessing
- Only extract what is explicitly stated
- Maintain a clean, queryable graph structure
- Avoid noise from ambiguous information

## Entity Types (STRICT)

### Allowed Types

Only these 6 entity types are permitted:

1. **Company**
   - Business organizations
   - Examples: TechCorp, DataSystems, QuantumAI
   - NOT: Individual people, departments, teams

2. **Platform**
   - Technology platforms and infrastructure
   - Examples: NovaCloud, CloudBase, DataPlatform
   - NOT: Generic software, tools without platform characteristics

3. **Service**
   - Products and services offered
   - Examples: "AI-powered analytics service", "storage service"
   - NOT: Internal processes, generic activities

4. **Partner**
   - Business partners and collaborators
   - Examples: Partner companies, strategic partners
   - NOT: Customers, users, suppliers (unless explicitly partners)

5. **Capability**
   - Technical or organizational capabilities
   - Examples: Machine Learning, Data Processing, Quantum Computing
   - NOT: User groups, beneficiaries, market segments

6. **Event**
   - Temporal milestones
   - Examples: Launch events, Acquisitions, Incorporations
   - NOT: Ongoing activities, processes

### Forbidden Entity Types

**DO NOT CREATE ENTITIES FOR:**

❌ People, users, roles, actors
- Examples: farmers, distributors, customers, users, employees, executives

❌ Beneficiaries or user groups
- Examples: "small farmers", "rural communities", "end users"

❌ Generic concepts
- Examples: "market", "industry", "sector" (unless they're specific companies)

❌ Activities or processes
- Examples: "distribution", "marketing", "sales" (unless they're specific services)

## Relations (STRICT)

### Allowed Relations

Only these neutral verbs are permitted:

1. **operates**
   - Company operates Platform
   - Example: "TechCorp operates NovaCloud"

2. **offers**
   - Company offers Service
   - Example: "TechCorp offers analytics service"

3. **launched**
   - Company/Event launched Service
   - Example: "TechCorp launched new service"

4. **acquired**
   - Company/Event acquired Company
   - Example: "TechCorp acquired StartupAI"

5. **partnered_with**
   - Company partnered with Partner
   - Example: "TechCorp partnered with DataSystems"

6. **integrated_with**
   - Service integrated with Platform
   - Example: "Analytics service integrated with NovaCloud"

7. **has_event**
   - Company has Event
   - Example: "TechCorp has Launch in 2020"

8. **described_in**
   - Entity described in Source
   - Example: "TechCorp described in chunk_001"

### Forbidden Relations

**DO NOT CREATE RELATIONS:**

❌ To people, users, or actors
- Bad: "Service serves farmers"
- Bad: "Platform helps users"

❌ Using benefit/target verbs
- Bad: "serves", "helps", "benefits", "targets", "enables for"

❌ Between entities and non-entities
- Bad: "Company → serves → customers" (customers not an entity type)

❌ Vague or ambiguous relations
- Bad: "related_to", "associated_with", "connected_to"

## Event Modeling (STRICT)

### Required Structure

Events must follow this pattern:

```
Company → has_event → Event
Event → launched/acquired → Entity
```

### Event Fields

1. **name** (required)
   - Descriptive name
   - Example: "Launch in 2020", "Acquisition of StartupAI in 2023"

2. **type** (required, must be one of):
   - `Launch` - Product/service launches
   - `Acquisition` - Company acquisitions
   - `Milestone` - Other significant events (incorporation, funding, etc.)

3. **year** (optional)
   - Integer year
   - Example: 2020, 2023

4. **company** (optional)
   - Name of the company associated with the event
   - Used to create Company → has_event → Event edge

5. **related_to** (optional)
   - Name of the entity the event relates to
   - Used to create Event → launched/acquired → Entity edge

6. **tags** (required)
   - Semantic labels
   - Must be meaningful: ["Launch"], ["Acquisition"], ["Milestone"]
   - NOT: ["event"], ["thing"], ["item"]

### Event Examples

**Good:**
```json
{
  "name": "Launch in 2020",
  "type": "Launch",
  "year": 2020,
  "company": "TechCorp",
  "related_to": "AI-powered analytics service",
  "tags": ["Launch"]
}
```

**Bad:**
```json
{
  "name": "Started serving farmers",  // ❌ Not a milestone
  "type": "Service",                   // ❌ Wrong type
  "year": null,
  "tags": ["activity"]                 // ❌ Not semantic
}
```

## Validation Rules

### Entity Validation

```python
valid_types = {"Company", "Platform", "Service", "Partner", "Capability", "Event"}

# Filter entities
entities = [e for e in entities if e.get("type") in valid_types]
```

### Relation Validation

```python
valid_relations = {
    "operates", "offers", "launched", "acquired",
    "partnered_with", "integrated_with", "has_event", "described_in"
}

# Filter relations
relations = [r for r in relations if r.get("relation") in valid_relations]
```

### Event Validation

```python
valid_event_types = {"Launch", "Acquisition", "Milestone"}

# Filter events
events = [
    e for e in events 
    if e.get("name") and e.get("type") in valid_event_types
]
```

## Ambiguity Handling

### When Information is Unclear

**Rule: Omit rather than guess**

Examples:

1. **Unclear entity type**
   - Text: "DataFlow helps farmers"
   - Extract: DataFlow (Company)
   - Omit: farmers (not an entity type)

2. **Unclear relationship**
   - Text: "Platform used by customers"
   - Extract: Platform entity
   - Omit: relationship to customers

3. **Unclear event**
   - Text: "Company started operations"
   - If year unclear: Omit event
   - If type unclear: Omit event

## LLM-Specific Constraints

The LLM extraction includes post-processing validation:

1. **Entity Type Filtering**
   - Remove any entities not in allowed types
   - Prevents hallucination of invalid types

2. **Relation Filtering**
   - Remove any relations not in allowed verbs
   - Prevents semantic drift

3. **Event Validation**
   - Ensure events have required fields
   - Ensure event types are valid
   - Remove malformed events

## Examples

### Good Extraction

**Text:**
```
TechCorp operates NovaCloud platform and offers an AI-powered analytics service.
TechCorp partnered with DataSystems in 2020.
```

**Extraction:**
```json
{
  "entities": [
    {"name": "TechCorp", "type": "Company", "attributes": {}},
    {"name": "NovaCloud", "type": "Platform", "attributes": {}},
    {"name": "AI-powered analytics service", "type": "Service", "attributes": {}},
    {"name": "DataSystems", "type": "Partner", "attributes": {}}
  ],
  "relations": [
    {"from": "TechCorp", "to": "NovaCloud", "relation": "operates"},
    {"from": "TechCorp", "to": "AI-powered analytics service", "relation": "offers"},
    {"from": "TechCorp", "to": "DataSystems", "relation": "partnered_with"}
  ],
  "events": []
}
```

### Bad Extraction (Corrected)

**Text:**
```
TechCorp's platform helps farmers manage their crops efficiently.
```

**Bad Extraction:**
```json
{
  "entities": [
    {"name": "TechCorp", "type": "Company"},
    {"name": "platform", "type": "Platform"},
    {"name": "farmers", "type": "User"},  // ❌ Invalid type
    {"name": "crops", "type": "Asset"}    // ❌ Invalid type
  ],
  "relations": [
    {"from": "platform", "to": "farmers", "relation": "helps"}  // ❌ Invalid relation
  ]
}
```

**Good Extraction:**
```json
{
  "entities": [
    {"name": "TechCorp", "type": "Company", "attributes": {}}
  ],
  "relations": [],
  "events": []
}
```

Note: Platform name is too generic, farmers and crops are not entity types, "helps" is not an allowed relation. Better to omit than guess.

## Testing Ontology Compliance

When testing extraction:

1. **Check entity types**
   - All entities must be in allowed types
   - No people, users, or actors

2. **Check relations**
   - All relations must use allowed verbs
   - No relations to non-entities

3. **Check events**
   - All events must have valid types
   - Events must connect properly

4. **Check for omissions**
   - Ambiguous information should be omitted
   - Better to have fewer, correct extractions

## Benefits of Strict Ontology

1. **Queryability**: Clean structure enables precise queries
2. **Consistency**: Same rules across all extraction methods
3. **Maintainability**: Clear boundaries prevent scope creep
4. **Reliability**: Predictable output structure
5. **Graph RAG Ready**: Structured for downstream retrieval

## Future Extensions

If the ontology needs to expand:

1. **Add new entity type**
   - Update allowed types list
   - Update validation rules
   - Document examples

2. **Add new relation**
   - Update allowed relations list
   - Define clear semantics
   - Update validation

3. **Add new event type**
   - Update allowed event types
   - Define structure requirements
   - Update validation

All extensions must maintain structural correctness principle.

---

**Remember: Structural Correctness > Semantic Richness**
