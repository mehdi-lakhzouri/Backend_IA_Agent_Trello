import langgraph as lg
from tools.add_etiquette_tool import apply_criticality_label_with_creation
from tools.add_comment_tool import add_comment_to_card

class WorkflowOrchestrator:
    def __init__(self):
        self.graph = lg.Graph()
        self.tools = {}

    def initialize_tools(self):
        """Initialiser les outils comme nœuds dans le graphe."""
        self.tools['apply_label'] = lg.FunctionNode(
            func=apply_criticality_label_with_creation,
            name='apply_label',
            description='Applique un label de criticité à une carte Trello.'
        )
        
        self.tools['add_comment'] = lg.FunctionNode(
            func=add_comment_to_card,
            name='add_comment',
            description='Ajoute un commentaire à une carte Trello.'
        )
        
    def create_workflow(self):
        """Crée le workflow avec des nodes LangGraph."""
        start_node = lg.StartNode()
        end_node = lg.EndNode()

        # Ajouter les outils comme nodes
        self.graph.add_nodes([start_node, end_node] + list(self.tools.values()))

        # Définir les connections entre les nodes
        self.graph.add_edge(start_node, self.tools['apply_label'])
        self.graph.add_edge(self.tools['apply_label'], self.tools['add_comment'])
        self.graph.add_edge(self.tools['add_comment'], end_node)

    def execute(self, context):
        """Exécuter le workflow défini."""
        self.graph.execute(context)
