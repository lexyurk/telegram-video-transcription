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
        prompt = f"""Analyze the following meeting transcript and determine what type of diagram would best represent the content.

Choose from these diagram types based on the meeting content:
- flowchart: For processes, workflows, decision trees, step-by-step procedures, or problem-solving discussions
- relationship: For connections between people, teams, concepts, stakeholders, or organizational interactions
- timeline: For chronological events, project phases, milestones, or sequential discussion points
- hierarchy: For organizational structures, reporting relationships, or categorized topics
- chart: For data comparisons, statistics, metrics, or quantitative information discussed

Consider what would be most valuable for someone reviewing this meeting:
- Are there clear processes or workflows discussed?
- Are there relationships between people, teams, or concepts that need visualization?
- Is there a timeline of events or project phases?
- Are there hierarchical structures or categorizations?
- Is there quantitative data that could be visualized?

Return ONLY the diagram type (one word in English: flowchart, relationship, timeline, hierarchy, or chart).

Meeting Transcript:
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
        """Extract nodes and edges for a flowchart focused on meeting content."""
        base_prompt = """Analyze the following meeting transcript and extract a flowchart structure that represents the key discussion flow, decision points, and action items.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on creating a meaningful flowchart that shows:
- Main discussion topics as process nodes
- Decision points and their outcomes
- Action items and next steps
- Key milestones or checkpoints mentioned
- Problem-solving steps discussed

Return a JSON object with two arrays:
1. "nodes": Array of objects with {"id": "unique_id", "label": "descriptive_label", "type": "start|process|decision|action|end"}
2. "edges": Array of arrays like ["from_id", "to_id", "optional_label"]

Guidelines:
- Use descriptive labels (up to 40 characters) that capture the essence of each step
- Include decision points with yes/no or multiple choice outcomes
- Show action items as distinct nodes
- Connect related discussion points logically
- Start with the main meeting topic and end with outcomes/next steps
- ALL LABELS AND TEXT MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "nodes": [
    {{"id": "start", "label": "Meeting: Project Status Review", "type": "start"}},
    {{"id": "status", "label": "Current Status Discussion", "type": "process"}},
    {{"id": "issues", "label": "Are there blockers?", "type": "decision"}},
    {{"id": "resolve", "label": "Plan Resolution Strategy", "type": "process"}},
    {{"id": "action1", "label": "Action: Update timeline", "type": "action"}},
    {{"id": "next", "label": "Schedule follow-up", "type": "action"}},
    {{"id": "end", "label": "Meeting concluded", "type": "end"}}
  ],
  "edges": [
    ["start", "status"],
    ["status", "issues"],
    ["issues", "resolve", "Yes"],
    ["issues", "next", "No"],
    ["resolve", "action1"],
    ["action1", "next"],
    ["next", "end"]
  ]
}}

Meeting Transcript:
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
                {"id": "start", "label": "Meeting Start", "type": "start"},
                {"id": "main", "label": "Main Discussion", "type": "process"},
                {"id": "action", "label": "Action Items Identified", "type": "action"},
                {"id": "end", "label": "Meeting End", "type": "end"}
            ], [("start", "main"), ("main", "action"), ("action", "end")]

    async def extract_relationship_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[List[str], List[Tuple]]:
        """Extract entities and relationships from meeting content."""
        base_prompt = """Analyze the following meeting transcript and extract relationships between people, teams, concepts, projects, or systems discussed.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying:
- People mentioned and their roles/interactions
- Teams or departments and their collaborations
- Projects or initiatives and their dependencies
- Systems or processes and their connections
- Concepts or topics and their relationships

Return a JSON object with two arrays:
1. "entities": Array of entity names (people, teams, projects, concepts, systems)
2. "relationships": Array of arrays like ["entity1", "entity2", weight, "relationship_type"] where:
   - weight is 1-5 (strength of relationship: 1=weak mention, 5=strong dependency)
   - relationship_type describes the connection (e.g., "collaborates with", "depends on", "reports to", "discussed together")

Guidelines:
- Use clear, descriptive entity names
- Include both people and non-people entities
- Show both direct and indirect relationships
- Prioritize relationships that are important for understanding the meeting outcomes
- ALL ENTITY NAMES AND RELATIONSHIP TYPES MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (names will be in the transcript's language):
{{
  "entities": ["Alice (PM)", "Bob (Dev)", "Marketing Team", "Project Alpha", "Database Migration", "Q4 Goals"],
  "relationships": [
    ["Alice (PM)", "Bob (Dev)", 4, "collaborates with"],
    ["Alice (PM)", "Project Alpha", 5, "manages"],
    ["Bob (Dev)", "Database Migration", 3, "responsible for"],
    ["Project Alpha", "Q4 Goals", 4, "contributes to"],
    ["Marketing Team", "Project Alpha", 2, "stakeholder in"]
  ]
}}

Meeting Transcript:
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
            return ["Participant A", "Participant B", "Main Topic"], [("Participant A", "Participant B", 3, "discussed with"), ("Participant A", "Main Topic", 4, "presented")]

    async def extract_timeline_data(self, transcript: str, custom_prompt: Optional[str] = None) -> List[Dict]:
        """Extract timeline events from meeting content."""
        base_prompt = """Analyze the following meeting transcript and extract chronological events, milestones, or sequential discussion points for a timeline.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying:
- Key milestones or deadlines mentioned
- Sequential steps in processes discussed
- Historical events or context referenced
- Future planned activities with dates
- Flow of discussion topics during the meeting

Return a JSON object with an "events" array containing objects with:
- "label": Clear description of the event (up to 50 characters)
- "order": Number indicating sequence (1, 2, 3, etc.)
- "type": Event type ("milestone", "deadline", "discussion", "decision", "action")
- "timeframe": Time reference if mentioned ("Q1", "next week", "completed", etc.)

Guidelines:
- Include both past and future events
- Show the progression of ideas or project phases
- Capture important decisions in chronological order
- Include action items with their timing
- ALL EVENT LABELS AND TIMEFRAMES MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "events": [
    {{"label": "Project kickoff completed", "order": 1, "type": "milestone", "timeframe": "last month"}},
    {{"label": "Requirements gathering discussed", "order": 2, "type": "discussion", "timeframe": "today"}},
    {{"label": "Design phase decision made", "order": 3, "type": "decision", "timeframe": "today"}},
    {{"label": "Prototype deadline set", "order": 4, "type": "deadline", "timeframe": "next Friday"}},
    {{"label": "Team review scheduled", "order": 5, "type": "action", "timeframe": "following week"}}
  ]
}}

Meeting Transcript:
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
                {"label": "Meeting started", "order": 1, "type": "discussion", "timeframe": "today"},
                {"label": "Main topics discussed", "order": 2, "type": "discussion", "timeframe": "today"},
                {"label": "Action items identified", "order": 3, "type": "action", "timeframe": "today"},
                {"label": "Next steps planned", "order": 4, "type": "action", "timeframe": "upcoming"}
            ]

    async def extract_hierarchy_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Dict:
        """Extract hierarchical structure from meeting content."""
        base_prompt = """Analyze the following meeting transcript and extract a hierarchical structure that represents organizational relationships, topic categorization, or decision tree discussed.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying:
- Organizational structures or reporting relationships
- Topic categorization or theme groupings
- Decision hierarchies or priority levels
- Project or task breakdown structures
- Stakeholder hierarchies or influence levels

Return a JSON object representing the hierarchy where each key has children as either:
- An object (for sub-hierarchies)
- An array (for leaf nodes)

Guidelines:
- Use clear, descriptive names for each level
- Show the most important/high-level items at the top
- Group related items together
- Include relevant context from the meeting
- ALL HIERARCHY NAMES AND LABELS MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "Project Leadership": {{
    "Project Manager": ["Alice - overall coordination", "Bob - technical lead"],
    "Stakeholders": ["Marketing team", "Executive sponsor"]
  }},
  "Main Discussion Topics": {{
    "Technical Issues": ["Database performance", "API integration"],
    "Timeline Concerns": ["Resource allocation", "Deadline feasibility"]
  }},
  "Action Items": {{
    "Immediate (this week)": ["Update project plan", "Schedule team meeting"],
    "Short-term (next month)": ["Complete prototype", "Conduct user testing"]
  }}
}}

Meeting Transcript:
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
            return {
                "Meeting Topics": {
                    "Main Discussion": ["Key points discussed", "Important decisions made"],
                    "Action Items": ["Tasks assigned", "Follow-up activities"]
                }
            }

    async def extract_chart_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[Dict, str]:
        """Extract data for charts from meeting content."""
        base_prompt = """Analyze the following meeting transcript and extract quantitative data that could be visualized as a chart.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying:
- Numerical data mentioned (budgets, timelines, metrics, percentages)
- Resource allocations or distributions
- Performance metrics or KPIs
- Survey results or feedback scores
- Progress indicators or completion rates
- Comparative data between options or alternatives

Return a JSON object with:
1. "data": Object with category names as keys and numbers as values
2. "chart_type": Either "bar", "pie", or "line" based on the data type
3. "title": Descriptive title for the chart
4. "unit": Unit of measurement (e.g., "hours", "dollars", "percentage", "count")

Guidelines:
- Extract actual numbers mentioned in the meeting
- Use meaningful category names
- Choose appropriate chart type for the data
- Include relevant context in the title
- ALL CATEGORY NAMES, TITLE, AND UNIT MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "data": {{"Development": 120, "Testing": 80, "Documentation": 40, "Deployment": 20}},
  "chart_type": "bar",
  "title": "Project Time Allocation (Hours)",
  "unit": "hours"
}}

Meeting Transcript:
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
            return {"Topic A": 30, "Topic B": 45, "Topic C": 25}, "bar" 