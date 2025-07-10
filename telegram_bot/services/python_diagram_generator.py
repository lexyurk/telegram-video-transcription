"""Python-based diagram generator for creating visual diagrams from transcripts."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import seaborn as sns
from loguru import logger

# Set matplotlib backend to Agg for headless environments
plt.switch_backend('Agg')

# Set style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class PythonDiagramGenerator:
    """Python-based diagram generator using matplotlib, networkx, and PIL."""

    def __init__(self):
        """Initialize the diagram generator."""
        # Enhanced color scheme for meeting visualizations
        self.colors = {
            'start': '#4CAF50',      # Green - start nodes
            'process': '#2196F3',    # Blue - process nodes
            'decision': '#FF9800',   # Orange - decision nodes
            'action': '#F44336',     # Red - action items
            'end': '#9C27B0',        # Purple - end nodes
            'milestone': '#795548',  # Brown - milestones
            'deadline': '#E91E63',   # Pink - deadlines
            'discussion': '#607D8B', # Blue-grey - discussions
            'primary': '#4CAF50',
            'secondary': '#81C784', 
            'accent': '#2E7D32',
            'background': '#f8f9fa',
            'text': '#212529',
            'border': '#45a049',
            'relationship': '#3F51B5'  # Indigo - relationships
        }
        
        # Figure settings
        self.figure_size = (19.2, 10.8)  # 1920x1080 at 100 DPI
        self.dpi = 100

    async def create_flowchart(self, nodes: List[Dict], edges: List[Tuple], title: str = "Process Flow") -> Optional[str]:
        """Create a flowchart diagram optimized for meeting content."""
        try:
            # Create directed graph
            G = nx.DiGraph()
            
            # Add nodes with attributes
            for node in nodes:
                G.add_node(node['id'], 
                          label=node['label'], 
                          node_type=node.get('type', 'process'))
            
            # Add edges
            for edge in edges:
                G.add_edge(edge[0], edge[1], label=edge[2] if len(edge) > 2 else "")
            
            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
            fig.patch.set_facecolor(self.colors['background'])
            ax.set_facecolor(self.colors['background'])
            
            # Generate layout with better spacing for meeting content
            pos = nx.spring_layout(G, k=4, iterations=100, seed=42)
            
            # Draw nodes with different colors and sizes based on type
            node_colors = []
            node_sizes = []
            for node_id, data in G.nodes(data=True):
                node_type = data.get('node_type', 'process')
                if node_type == 'start':
                    node_colors.append(self.colors['start'])
                    node_sizes.append(3500)
                elif node_type == 'end':
                    node_colors.append(self.colors['end'])
                    node_sizes.append(3500)
                elif node_type == 'decision':
                    node_colors.append(self.colors['decision'])
                    node_sizes.append(4000)
                elif node_type == 'action':
                    node_colors.append(self.colors['action'])
                    node_sizes.append(3800)
                else:  # process
                    node_colors.append(self.colors['process'])
                    node_sizes.append(3200)
            
            # Draw nodes
            nx.draw_networkx_nodes(
                G, pos, 
                node_color=node_colors,
                node_size=node_sizes,
                alpha=0.9,
                ax=ax
            )
            
            # Draw edges with improved styling
            nx.draw_networkx_edges(
                G, pos,
                edge_color=self.colors['accent'],
                arrows=True,
                arrowsize=25,
                arrowstyle='->',
                width=2.5,
                alpha=0.8,
                ax=ax
            )
            
            # Draw labels with better formatting
            labels = {}
            for node_id, data in G.nodes(data=True):
                label = data['label']
                # Break long labels into multiple lines
                if len(label) > 25:
                    words = label.split()
                    lines = []
                    current_line = []
                    for word in words:
                        if len(' '.join(current_line + [word])) <= 25:
                            current_line.append(word)
                        else:
                            if current_line:
                                lines.append(' '.join(current_line))
                                current_line = [word]
                            else:
                                lines.append(word)
                    if current_line:
                        lines.append(' '.join(current_line))
                    label = '\n'.join(lines)
                labels[node_id] = label
            
            nx.draw_networkx_labels(
                G, pos, labels,
                font_size=9,
                font_color='white',
                font_weight='bold',
                ax=ax
            )
            
            # Draw edge labels
            edge_labels = nx.get_edge_attributes(G, 'label')
            if edge_labels:
                nx.draw_networkx_edge_labels(
                    G, pos, edge_labels,
                    font_size=8,
                    font_color=self.colors['text'],
                    bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8),
                    ax=ax
                )
            
            # Add legend for node types
            legend_elements = []
            unique_types = set(data.get('node_type', 'process') for _, data in G.nodes(data=True))
            for node_type in unique_types:
                color = self.colors.get(node_type, self.colors['process'])
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                                markerfacecolor=color, markersize=10, 
                                                label=node_type.capitalize()))
            
            if legend_elements:
                ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
            
            # Set title
            ax.set_title(title, fontsize=18, fontweight='bold', color=self.colors['text'], pad=25)
            ax.axis('off')
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/python_diagram_{timestamp}.png"
            
            plt.tight_layout()
            plt.savefig(
                output_path,
                facecolor=self.colors['background'],
                edgecolor='none',
                bbox_inches='tight',
                dpi=self.dpi,
                format='png'
            )
            plt.close(fig)
            
            logger.info(f"Successfully created flowchart: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating flowchart: {e}", exc_info=True)
            return None

    async def create_relationship_diagram(self, entities: List[str], relationships: List[Tuple], title: str = "Relationships") -> Optional[str]:
        """Create a relationship/network diagram for meeting stakeholders and concepts."""
        try:
            # Create undirected graph for relationships
            G = nx.Graph()
            
            # Add nodes
            G.add_nodes_from(entities)
            
            # Add edges with weights and relationship types
            edge_labels = {}
            for rel in relationships:
                if len(rel) >= 2:
                    weight = rel[2] if len(rel) > 2 and isinstance(rel[2], (int, float)) else 1
                    rel_type = rel[3] if len(rel) > 3 else ""
                    G.add_edge(rel[0], rel[1], weight=weight, rel_type=rel_type)
                    if rel_type:
                        edge_labels[(rel[0], rel[1])] = rel_type
            
            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
            fig.patch.set_facecolor(self.colors['background'])
            ax.set_facecolor(self.colors['background'])
            
            # Generate layout
            if len(G.nodes()) <= 10:
                pos = nx.spring_layout(G, k=3, iterations=100, seed=42)
            else:
                pos = nx.kamada_kawai_layout(G)
            
            # Calculate node sizes based on degree centrality
            centrality = nx.degree_centrality(G)
            node_sizes = [2500 + centrality[node] * 3000 for node in G.nodes()]
            
            # Color nodes based on entity type (people vs concepts)
            node_colors = []
            for entity in entities:
                if any(indicator in entity.lower() for indicator in ['(', 'team', 'dept', 'project']):
                    node_colors.append(self.colors['secondary'])
                else:
                    node_colors.append(self.colors['primary'])
            
            # Draw nodes
            nx.draw_networkx_nodes(
                G, pos,
                node_color=node_colors,
                node_size=node_sizes,
                alpha=0.9,
                ax=ax
            )
            
            # Draw edges with varying thickness based on weight
            edges = G.edges(data=True)
            widths = [edge[2].get('weight', 1) * 2 for edge in edges]
            
            nx.draw_networkx_edges(
                G, pos,
                width=widths,
                edge_color=self.colors['relationship'],
                alpha=0.6,
                ax=ax
            )
            
            # Draw node labels
            labels = {}
            for entity in entities:
                # Truncate long entity names
                if len(entity) > 15:
                    labels[entity] = entity[:12] + "..."
                else:
                    labels[entity] = entity
                    
            nx.draw_networkx_labels(
                G, pos, labels,
                font_size=9,
                font_color='white',
                font_weight='bold',
                ax=ax
            )
            
            # Draw edge labels (relationship types)
            if edge_labels:
                nx.draw_networkx_edge_labels(
                    G, pos, edge_labels,
                    font_size=7,
                    font_color=self.colors['text'],
                    bbox=dict(boxstyle="round,pad=0.1", facecolor='white', alpha=0.8),
                    ax=ax
                )
            
            # Set title
            ax.set_title(title, fontsize=18, fontweight='bold', color=self.colors['text'], pad=25)
            ax.axis('off')
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/python_diagram_{timestamp}.png"
            
            plt.tight_layout()
            plt.savefig(
                output_path,
                facecolor=self.colors['background'],
                edgecolor='none',
                bbox_inches='tight',
                dpi=self.dpi,
                format='png'
            )
            plt.close(fig)
            
            logger.info(f"Successfully created relationship diagram: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating relationship diagram: {e}", exc_info=True)
            return None

    async def create_timeline_diagram(self, events: List[Dict], title: str = "Timeline") -> Optional[str]:
        """Create a timeline diagram for meeting events and milestones."""
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
            fig.patch.set_facecolor(self.colors['background'])
            ax.set_facecolor(self.colors['background'])
            
            # Sort events by order if provided, otherwise use list order
            sorted_events = sorted(events, key=lambda x: x.get('order', events.index(x)))
            
            # Create timeline
            y_pos = 0.5
            x_positions = []
            labels = []
            colors = []
            
            for i, event in enumerate(sorted_events):
                x_pos = i / (len(sorted_events) - 1) if len(sorted_events) > 1 else 0.5
                x_positions.append(x_pos)
                labels.append(event['label'])
                
                # Color based on event type
                event_type = event.get('type', 'discussion')
                colors.append(self.colors.get(event_type, self.colors['discussion']))
            
            # Draw timeline line
            ax.plot([0, 1], [y_pos, y_pos], color=self.colors['accent'], linewidth=6, alpha=0.8)
            
            # Draw event points and labels
            for i, (x_pos, label, color) in enumerate(zip(x_positions, labels, colors)):
                # Draw point
                ax.scatter(x_pos, y_pos, s=300, color=color, zorder=5, alpha=0.9, 
                          edgecolors='white', linewidth=2)
                
                # Draw label with better positioning
                y_offset = 0.15 if i % 2 == 0 else -0.15
                
                # Add timeframe information if available
                event = sorted_events[i]
                full_label = label
                if event.get('timeframe'):
                    full_label = f"{label}\n({event['timeframe']})"
                
                ax.annotate(
                    full_label,
                    (x_pos, y_pos),
                    xytext=(x_pos, y_pos + y_offset),
                    ha='center',
                    va='bottom' if y_offset > 0 else 'top',
                    fontsize=10,
                    fontweight='bold',
                    color=self.colors['text'],
                    bbox=dict(boxstyle="round,pad=0.4", facecolor=color, alpha=0.8, 
                             edgecolor='white', linewidth=1),
                    arrowprops=dict(arrowstyle='->', color=self.colors['accent'], 
                                  alpha=0.8, lw=2)
                )
            
            # Add legend for event types
            legend_elements = []
            unique_types = set(event.get('type', 'discussion') for event in sorted_events)
            for event_type in unique_types:
                color = self.colors.get(event_type, self.colors['discussion'])
                legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                                markerfacecolor=color, markersize=12, 
                                                label=event_type.capitalize()))
            
            if legend_elements:
                ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1))
            
            # Set title
            ax.set_title(title, fontsize=18, fontweight='bold', color=self.colors['text'], pad=25)
            
            # Clean up axes
            ax.set_xlim(-0.1, 1.1)
            ax.set_ylim(-0.1, 1.1)
            ax.axis('off')
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/python_diagram_{timestamp}.png"
            
            plt.tight_layout()
            plt.savefig(
                output_path,
                facecolor=self.colors['background'],
                edgecolor='none',
                bbox_inches='tight',
                dpi=self.dpi,
                format='png'
            )
            plt.close(fig)
            
            logger.info(f"Successfully created timeline diagram: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating timeline diagram: {e}", exc_info=True)
            return None

    async def create_hierarchy_diagram(self, hierarchy: Dict, title: str = "Hierarchy") -> Optional[str]:
        """Create a hierarchical/organizational diagram."""
        try:
            # Create directed graph
            G = nx.DiGraph()
            
            def add_hierarchy_to_graph(parent, children_dict, graph):
                if isinstance(children_dict, dict):
                    for child, grandchildren in children_dict.items():
                        graph.add_edge(parent, child)
                        add_hierarchy_to_graph(child, grandchildren, graph)
                elif isinstance(children_dict, list):
                    for child in children_dict:
                        graph.add_edge(parent, child)
            
            # Add root and build hierarchy
            root = list(hierarchy.keys())[0]
            G.add_node(root)
            add_hierarchy_to_graph(root, hierarchy[root], G)
            
            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
            fig.patch.set_facecolor(self.colors['background'])
            ax.set_facecolor(self.colors['background'])
            
            # Use hierarchical layout
            pos = nx.nx_agraph.graphviz_layout(G, prog='dot') if hasattr(nx, 'nx_agraph') else nx.spring_layout(G, k=3, iterations=50)
            
            # Draw nodes with different colors based on hierarchy level
            levels = {}
            for node in G.nodes():
                try:
                    levels[node] = nx.shortest_path_length(G, root, node)
                except:
                    levels[node] = 0
            
            max_level = max(levels.values()) if levels else 0
            
            for level in range(max_level + 1):
                level_nodes = [node for node, node_level in levels.items() if node_level == level]
                color_intensity = 1 - (level * 0.2)
                color = plt.cm.Greens(max(0.3, color_intensity))
                
                nx.draw_networkx_nodes(
                    G, pos, nodelist=level_nodes,
                    node_color=[color],
                    node_size=2500,
                    alpha=0.9,
                    ax=ax
                )
            
            # Draw edges
            nx.draw_networkx_edges(
                G, pos,
                edge_color=self.colors['accent'],
                arrows=True,
                arrowsize=15,
                arrowstyle='->',
                width=2,
                alpha=0.7,
                ax=ax
            )
            
            # Draw labels
            nx.draw_networkx_labels(
                G, pos,
                font_size=9,
                font_color=self.colors['text'],
                font_weight='bold',
                ax=ax
            )
            
            # Set title
            ax.set_title(title, fontsize=16, fontweight='bold', color=self.colors['text'], pad=20)
            ax.axis('off')
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/python_diagram_{timestamp}.png"
            
            plt.tight_layout()
            plt.savefig(
                output_path,
                facecolor=self.colors['background'],
                edgecolor='none',
                bbox_inches='tight',
                dpi=self.dpi,
                format='png'
            )
            plt.close(fig)
            
            logger.info(f"Successfully created hierarchy diagram: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating hierarchy diagram: {e}", exc_info=True)
            return None

    async def create_simple_chart(self, data: Dict, chart_type: str = "bar", title: str = "Chart") -> Optional[str]:
        """Create a simple chart (bar, pie, etc.) for meeting data."""
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
            fig.patch.set_facecolor(self.colors['background'])
            ax.set_facecolor(self.colors['background'])
            
            labels = list(data.keys())
            values = list(data.values())
            
            if chart_type == "pie":
                colors = sns.color_palette("husl", len(labels))
                wedges, texts, autotexts = ax.pie(
                    values, labels=labels, autopct='%1.1f%%',
                    colors=colors, startangle=90
                )
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(10)
                    
            elif chart_type == "line":
                # Line chart for time series data
                colors = sns.color_palette("husl", 1)
                ax.plot(labels, values, marker='o', linewidth=3, markersize=8, 
                       color=colors[0], alpha=0.8)
                ax.grid(True, alpha=0.3)
                ax.set_xlabel('Categories', fontweight='bold', fontsize=12)
                ax.set_ylabel('Values', fontweight='bold', fontsize=12)
                plt.xticks(rotation=45, ha='right')
                
            else:  # bar chart
                colors = sns.color_palette("husl", len(labels))
                bars = ax.bar(labels, values, color=colors, alpha=0.8)
                
                # Add value labels on bars
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.1f}',
                           ha='center', va='bottom', fontweight='bold', fontsize=10)
                
                ax.set_xlabel('Categories', fontweight='bold', fontsize=12)
                ax.set_ylabel('Values', fontweight='bold', fontsize=12)
                ax.grid(True, alpha=0.3, axis='y')
                plt.xticks(rotation=45, ha='right')
            
            # Set title
            ax.set_title(title, fontsize=18, fontweight='bold', color=self.colors['text'], pad=25)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/python_diagram_{timestamp}.png"
            
            plt.tight_layout()
            plt.savefig(
                output_path,
                facecolor=self.colors['background'],
                edgecolor='none',
                bbox_inches='tight',
                dpi=self.dpi,
                format='png'
            )
            plt.close(fig)
            
            logger.info(f"Successfully created {chart_type} chart: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating {chart_type} chart: {e}", exc_info=True)
            return None 