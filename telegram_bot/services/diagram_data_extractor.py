"""AI-powered diagram data extractor for analyzing transcripts and extracting diagram data."""

import json
from typing import Dict, List, Optional, Tuple

from loguru import logger

from telegram_bot.services.ai_model import AIModel


class DiagramDataExtractor:
    """Extract structured diagram data from transcripts using AI."""

    def __init__(self, ai_model: AIModel):
        """Initialize the data extractor."""
        self.ai_model = ai_model

    async def analyze_transcript_for_diagram_type(self, transcript: str) -> str:
        """Analyze transcript and determine the best diagram type."""
        prompt = f"""Analyze the following transcript and determine what type of diagram would best represent the content.

Choose from these diagram types:
- flowchart: For processes, workflows, decision trees, step-by-step procedures
- relationship: For connections between people, entities, concepts, or organizations
- timeline: For chronological events, sequences, or historical progression
- hierarchy: For organizational structures, command chains, categorizations
- chart: For data comparisons, statistics, or quantitative information

Return ONLY the diagram type (one word).

Transcript:
{transcript}"""

        try:
            result = await self.ai_model.generate_text(prompt)
            diagram_type = result.strip().lower()
            
            # Validate result
            valid_types = ['flowchart', 'relationship', 'timeline', 'hierarchy', 'chart']
            if diagram_type in valid_types:
                logger.info(f"Determined diagram type: {diagram_type}")
                return diagram_type
            else:
                logger.warning(f"Invalid diagram type returned: {diagram_type}, defaulting to flowchart")
                return 'flowchart'
                
        except Exception as e:
            logger.error(f"Error determining diagram type: {e}")
            return 'flowchart'  # Default fallback

    async def extract_flowchart_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[List[Dict], List[Tuple]]:
        """Extract nodes and edges for a flowchart."""
        base_prompt = """Analyze the following transcript and extract a flowchart structure.

Return a JSON object with two arrays:
1. "nodes": Array of objects with {"id": "unique_id", "label": "short_label", "type": "start|process|decision|end"}
2. "edges": Array of arrays like ["from_id", "to_id", "optional_label"]

Keep labels short (max 15 characters). Create a logical flow showing the main process or decision points.

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format:
{{
  "nodes": [
    {{"id": "start", "label": "Begin", "type": "start"}},
    {{"id": "process1", "label": "Check Input", "type": "process"}},
    {{"id": "decision1", "label": "Valid?", "type": "decision"}},
    {{"id": "end", "label": "Done", "type": "end"}}
  ],
  "edges": [
    ["start", "process1"],
    ["process1", "decision1"],
    ["decision1", "end", "Yes"]
  ]
}}

Transcript:
{transcript}"""

        try:
            result = await self.ai_model.generate_text(base_prompt)
            
            # Clean up result (remove markdown if present)
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            data = json.loads(result)
            nodes = data.get('nodes', [])
            edges = data.get('edges', [])
            
            # Convert edge format
            formatted_edges = []
            for edge in edges:
                if len(edge) >= 2:
                    formatted_edges.append(tuple(edge))
            
            logger.info(f"Extracted flowchart: {len(nodes)} nodes, {len(formatted_edges)} edges")
            return nodes, formatted_edges
            
        except Exception as e:
            logger.error(f"Error extracting flowchart data: {e}")
            # Return simple fallback structure
            return [
                {"id": "start", "label": "Start", "type": "start"},
                {"id": "main", "label": "Main Process", "type": "process"},
                {"id": "end", "label": "End", "type": "end"}
            ], [("start", "main"), ("main", "end")]

    async def extract_relationship_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[List[str], List[Tuple]]:
        """Extract entities and relationships."""
        base_prompt = """Analyze the following transcript and extract relationships between entities (people, organizations, concepts, etc.).

Return a JSON object with two arrays:
1. "entities": Array of entity names (people, organizations, concepts)
2. "relationships": Array of arrays like ["entity1", "entity2", weight] where weight is 1-5 (strength of relationship)

Keep entity names short and clear.

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format:
{{
  "entities": ["Alice", "Bob", "Company A", "Project X"],
  "relationships": [
    ["Alice", "Bob", 3],
    ["Alice", "Company A", 5],
    ["Bob", "Project X", 2]
  ]
}}

Transcript:
{transcript}"""

        try:
            result = await self.ai_model.generate_text(base_prompt)
            
            # Clean up result
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            data = json.loads(result)
            entities = data.get('entities', [])
            relationships = data.get('relationships', [])
            
            # Convert relationship format
            formatted_relationships = []
            for rel in relationships:
                if len(rel) >= 2:
                    formatted_relationships.append(tuple(rel))
            
            logger.info(f"Extracted relationships: {len(entities)} entities, {len(formatted_relationships)} relationships")
            return entities, formatted_relationships
            
        except Exception as e:
            logger.error(f"Error extracting relationship data: {e}")
            # Return simple fallback
            return ["Entity A", "Entity B"], [("Entity A", "Entity B", 1)]

    async def extract_timeline_data(self, transcript: str, custom_prompt: Optional[str] = None) -> List[Dict]:
        """Extract timeline events."""
        base_prompt = """Analyze the following transcript and extract chronological events for a timeline.

Return a JSON object with an "events" array containing objects with:
- "label": Short description of the event (max 20 characters)
- "order": Number indicating sequence (1, 2, 3, etc.)

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format:
{{
  "events": [
    {{"label": "Project Start", "order": 1}},
    {{"label": "First Review", "order": 2}},
    {{"label": "Launch", "order": 3}}
  ]
}}

Transcript:
{transcript}"""

        try:
            result = await self.ai_model.generate_text(base_prompt)
            
            # Clean up result
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            data = json.loads(result)
            events = data.get('events', [])
            
            logger.info(f"Extracted timeline: {len(events)} events")
            return events
            
        except Exception as e:
            logger.error(f"Error extracting timeline data: {e}")
            # Return simple fallback
            return [
                {"label": "Start", "order": 1},
                {"label": "Middle", "order": 2},
                {"label": "End", "order": 3}
            ]

    async def extract_hierarchy_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Dict:
        """Extract hierarchical structure."""
        base_prompt = """Analyze the following transcript and extract a hierarchical structure (organizational chart, categorization, etc.).

Return a JSON object representing the hierarchy where each key has children as either:
- An object (for sub-hierarchies)
- An array (for leaf nodes)

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format:
{{
  "CEO": {{
    "VP Engineering": ["Team Lead A", "Team Lead B"],
    "VP Sales": ["Sales Rep 1", "Sales Rep 2"]
  }}
}}

Transcript:
{transcript}"""

        try:
            result = await self.ai_model.generate_text(base_prompt)
            
            # Clean up result
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            data = json.loads(result)
            
            logger.info(f"Extracted hierarchy: {len(data)} root nodes")
            return data
            
        except Exception as e:
            logger.error(f"Error extracting hierarchy data: {e}")
            # Return simple fallback
            return {"Root": ["Child A", "Child B"]}

    async def extract_chart_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[Dict, str]:
        """Extract data for charts."""
        base_prompt = """Analyze the following transcript and extract quantitative data for a chart.

Return a JSON object with:
1. "data": Object with category names as keys and numbers as values
2. "chart_type": Either "bar" or "pie"

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format:
{{
  "data": {{"Category A": 25, "Category B": 45, "Category C": 30}},
  "chart_type": "bar"
}}

Transcript:
{transcript}"""

        try:
            result = await self.ai_model.generate_text(base_prompt)
            
            # Clean up result
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()
            
            parsed_data = json.loads(result)
            chart_data = parsed_data.get('data', {})
            chart_type = parsed_data.get('chart_type', 'bar')
            
            logger.info(f"Extracted chart data: {len(chart_data)} categories, type: {chart_type}")
            return chart_data, chart_type
            
        except Exception as e:
            logger.error(f"Error extracting chart data: {e}")
            # Return simple fallback
            return {"Item A": 30, "Item B": 70}, "bar" 