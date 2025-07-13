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
        prompt = f"""Analyze the following technical discussion transcript and determine what type of diagram would best visualize the SYSTEMS and ARCHITECTURE discussed.

Choose from these diagram types based on the technical content:
- flowchart: For system architectures, data flows, API interactions, microservices, system components and their interactions
- relationship: For database schemas, entity relationships, service dependencies, module interactions, or technology stack connections
- timeline: For deployment schedules, release plans, migration timelines, or development phases
- hierarchy: For system layers, component hierarchies, inheritance structures, or nested configurations
- chart: For performance metrics, resource usage, scaling data, or technical comparisons

Focus on extracting TECHNICAL SYSTEMS, not conversation flow:
- Are there system components, services, or APIs discussed?
- Are there data flows or integration points between systems?
- Are there databases, schemas, or data relationships mentioned?
- Are there technical dependencies or architectural layers?
- Are there performance metrics or technical comparisons?

Return ONLY the diagram type (one word in English: flowchart, relationship, timeline, hierarchy, or chart).

Technical Discussion Transcript:
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
        """Extract nodes and edges for a flowchart focused on system architecture."""
        base_prompt = """Analyze the following technical discussion and extract a system architecture diagram showing the TECHNICAL COMPONENTS and their interactions.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying and visualizing:
- System components (services, APIs, databases, queues, caches)
- Data flows between components
- External integrations and third-party services
- Processing pipelines and workflows
- Technical decision points (load balancers, routers, gateways)

Return a JSON object with two arrays:
1. "nodes": Array of objects with {"id": "unique_id", "label": "component_name", "type": "service|database|api|queue|cache|external|gateway"}
2. "edges": Array of arrays like ["from_id", "to_id", "data_flow_label"]

Guidelines:
- Extract ACTUAL SYSTEM COMPONENTS mentioned, not discussion topics
- Use technical component names (e.g., "PostgreSQL", "Redis Cache", "Auth Service")
- Show data flow directions with meaningful labels (e.g., "HTTP Request", "Event Stream", "SQL Query")
- Group related services logically
- Focus on technical architecture, not people or process
- ALL LABELS AND TEXT MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "nodes": [
    {{"id": "frontend", "label": "React Frontend", "type": "service"}},
    {{"id": "api_gateway", "label": "API Gateway", "type": "gateway"}},
    {{"id": "auth_service", "label": "Auth Service", "type": "service"}},
    {{"id": "user_service", "label": "User Service", "type": "service"}},
    {{"id": "postgres_db", "label": "PostgreSQL", "type": "database"}},
    {{"id": "redis_cache", "label": "Redis Cache", "type": "cache"}},
    {{"id": "kafka", "label": "Kafka Queue", "type": "queue"}},
    {{"id": "payment_api", "label": "Stripe API", "type": "external"}}
  ],
  "edges": [
    ["frontend", "api_gateway", "HTTPS"],
    ["api_gateway", "auth_service", "JWT Validation"],
    ["api_gateway", "user_service", "REST API"],
    ["user_service", "postgres_db", "SQL Query"],
    ["user_service", "redis_cache", "Cache Read/Write"],
    ["user_service", "kafka", "Event Publish"],
    ["user_service", "payment_api", "Payment Request"]
  ]
}}

Technical Discussion Transcript:
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
                {"id": "client", "label": "Client App", "type": "service"},
                {"id": "server", "label": "Backend Server", "type": "service"},
                {"id": "database", "label": "Database", "type": "database"},
                {"id": "cache", "label": "Cache Layer", "type": "cache"}
            ], [("client", "server"), ("server", "database"), ("server", "cache")]

    async def extract_relationship_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[List[str], List[Tuple]]:
        """Extract technical entities and their relationships."""
        base_prompt = """Analyze the following technical discussion and extract relationships between technical components, systems, databases, and services.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying TECHNICAL relationships:
- Database tables and their foreign key relationships
- Services and their dependencies
- APIs and their consumers
- Data models and their associations
- Modules/packages and their imports
- Technology stack layers and interactions

Return a JSON object with two arrays:
1. "entities": Array of technical entity names (services, databases, tables, APIs, modules)
2. "relationships": Array of arrays like ["entity1", "entity2", weight, "relationship_type"] where:
   - weight is 1-5 (strength of coupling: 1=loose, 5=tight dependency)
   - relationship_type describes the technical relationship (e.g., "calls API", "reads from", "publishes to", "inherits from", "implements")

Guidelines:
- Extract TECHNICAL ENTITIES only (no people or teams)
- Use specific technical names (e.g., "users_table", "AuthenticationAPI", "PaymentService")
- Show technical dependencies and data flows
- Focus on system architecture relationships
- ALL ENTITY NAMES AND RELATIONSHIP TYPES MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (names will be in the transcript's language):
{{
  "entities": ["UserService", "AuthService", "users_table", "sessions_table", "RedisCache", "PostgreSQL", "REST API", "JWT Token"],
  "relationships": [
    ["UserService", "AuthService", 4, "calls API"],
    ["UserService", "users_table", 5, "reads/writes"],
    ["AuthService", "sessions_table", 5, "manages"],
    ["AuthService", "JWT Token", 4, "generates"],
    ["UserService", "RedisCache", 3, "caches to"],
    ["users_table", "PostgreSQL", 5, "stored in"],
    ["sessions_table", "PostgreSQL", 5, "stored in"],
    ["REST API", "JWT Token", 4, "secured by"]
  ]
}}

Technical Discussion Transcript:
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
            return ["Frontend", "Backend API", "Database"], [("Frontend", "Backend API", 4, "calls"), ("Backend API", "Database", 5, "queries")]

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
        """Extract technical hierarchical structure from discussion."""
        base_prompt = """Analyze the following technical discussion and extract a hierarchical structure representing the SYSTEM ARCHITECTURE LAYERS or COMPONENT HIERARCHY.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying TECHNICAL hierarchies:
- System architecture layers (presentation, business logic, data layer)
- Component hierarchies (parent services and their sub-components)
- Technology stack layers (frontend frameworks, backend, infrastructure)
- Module/package structures and dependencies
- API endpoint hierarchies and resources
- Configuration hierarchies or nested settings

Return a JSON object representing the technical hierarchy where each key has children as either:
- An object (for sub-hierarchies)
- An array (for leaf components)

Guidelines:
- Extract TECHNICAL COMPONENTS AND LAYERS only
- Use specific technical names (e.g., "API Gateway", "Microservices", "Data Access Layer")
- Show architectural layers from high-level to detailed
- Group related technical components together
- ALL HIERARCHY NAMES AND LABELS MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "Frontend Layer": {{
    "React Application": ["Components", "State Management (Redux)", "API Client"],
    "Mobile Apps": ["iOS (Swift)", "Android (Kotlin)", "React Native Shared"]
  }},
  "Backend Services": {{
    "API Gateway": ["Authentication", "Rate Limiting", "Request Routing"],
    "Microservices": {{
      "User Service": ["User CRUD", "Profile Management", "Preferences"],
      "Order Service": ["Order Processing", "Payment Integration", "Inventory Check"],
      "Notification Service": ["Email Sender", "SMS Gateway", "Push Notifications"]
    }}
  }},
  "Data Layer": {{
    "Databases": ["PostgreSQL (Primary)", "MongoDB (Documents)", "Redis (Cache)"],
    "Message Queue": ["Kafka Topics", "Event Consumers", "Dead Letter Queue"]
  }},
  "Infrastructure": {{
    "Kubernetes Cluster": ["Pods", "Services", "Ingress Controllers"],
    "Monitoring": ["Prometheus", "Grafana", "ELK Stack"]
  }}
}}

Technical Discussion Transcript:
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
                "Application Layer": {
                    "Frontend": ["UI Components", "Client Logic"],
                    "Backend": ["API Endpoints", "Business Logic"]
                },
                "Data Layer": ["Database", "Cache"]
            }

    async def extract_chart_data(self, transcript: str, custom_prompt: Optional[str] = None) -> Tuple[Dict, str]:
        """Extract technical metrics and performance data for visualization."""
        base_prompt = """Analyze the following technical discussion and extract quantitative metrics or performance data that could be visualized as a chart.

IMPORTANT: Respond in the SAME LANGUAGE as the transcript. If the transcript is in Russian, respond in Russian. If in Spanish, respond in Spanish. If in English, respond in English, etc.

Focus on identifying TECHNICAL METRICS:
- Performance benchmarks (response times, throughput, latency)
- Resource utilization (CPU, memory, disk usage)
- System metrics (requests/sec, error rates, uptime)
- Code quality metrics (test coverage, code complexity, bug counts)
- Infrastructure costs or resource allocation
- Scalability metrics (concurrent users, data volume)

Return a JSON object with:
1. "data": Object with metric names as keys and numbers as values
2. "chart_type": Either "bar", "pie", or "line" based on the metric type
3. "title": Technical title for the chart
4. "unit": Unit of measurement (e.g., "ms", "requests/sec", "GB", "%")

Guidelines:
- Extract ACTUAL TECHNICAL METRICS mentioned
- Use precise technical terminology
- Choose chart type appropriate for the metric
- Include measurement units in the title
- ALL METRIC NAMES, TITLE, AND UNIT MUST BE IN THE SAME LANGUAGE AS THE TRANSCRIPT

"""
        
        if custom_prompt:
            base_prompt += f"\nCustom requirements: {custom_prompt}\n"
        
        base_prompt += f"""
Example format (labels will be in the transcript's language):
{{
  "data": {{"API Gateway": 45, "Auth Service": 120, "User Service": 85, "Database": 250}},
  "chart_type": "bar",
  "title": "Service Response Times",
  "unit": "ms"
}}

Technical Discussion Transcript:
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
            return {"Service A": 100, "Service B": 150, "Service C": 75}, "bar" 