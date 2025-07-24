"""
Service d'analyse de criticité des cards Trello utilisant l'API Gemini.
"""

import os
import google.generativeai as genai
from flask import current_app
from typing import Dict, List, Any
import json
from app.database.chroma import ChromaDBManager


class CriticalityAnalyzer:
    """Analyse la criticité des cards Trello en utilisant Gemini 1.5 Flash."""
    
    def __init__(self):
        """Initialise le service avec la configuration Gemini."""
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY non configurée")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.chroma_manager = ChromaDBManager()
        
    def _get_application_context(self) -> str:
        """
        Récupère le contexte de l'application depuis les documents uploadés.
        """
        try:
            # Récupérer tous les documents uploadés dans ChromaDB
            # En cherchant par métadonnées des fichiers uploadés
            collection = self.chroma_manager.get_collection()
            
            # Récupérer tous les documents (chunks) stockés
            results = collection.get(
                include=['documents', 'metadatas']
            )
            
            if not results or not results.get('documents'):
                current_app.logger.warning("Aucun document trouvé dans ChromaDB")
                return self._get_default_context()
            
            # Grouper les chunks par fichier original
            files_content = {}
            documents = results.get('documents', [])
            metadatas = results.get('metadatas', [])
            
            # Ensure documents and metadatas are lists, not None
            if documents is None:
                documents = []
            if metadatas is None:
                metadatas = []

            for i, content in enumerate(documents):
                if i < len(metadatas):
                    metadata = metadatas[i] if metadatas[i] is not None else {}
                    filename = metadata.get('filename', 'unknown')
                    document_id = metadata.get('document_id')
                    chunk_index = metadata.get('chunk_index', 0)
                    
                    if document_id not in files_content:
                        files_content[document_id] = {
                            'filename': filename,
                            'chunks': []
                        }
                    
                    files_content[document_id]['chunks'].append({
                        'index': chunk_index,
                        'content': content
                    })
            
            # Reconstituer le contenu complet de chaque fichier
            context_parts = []
            for doc_id, file_info in files_content.items():
                # Trier les chunks par index et reconstituer le contenu
                sorted_chunks = sorted(file_info['chunks'], key=lambda x: x['index'])
                full_content = '\n'.join([chunk['content'] for chunk in sorted_chunks])
                
                # Ajouter le nom du fichier et son contenu
                context_parts.append(f"=== FICHIER: {file_info['filename']} ===\n{full_content}")
            
            if context_parts:
                current_app.logger.debug(f"[CRITICALITY] Consultation de fichier de description effectuée: {len(files_content)} fichier(s) utilisé(s)")
                return "\n\n".join(context_parts)
            else:
                current_app.logger.warning("[CRITICALITY] Aucun fichier de description consulté, utilisation du contexte par défaut.")
                return self._get_default_context()
                
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération du contexte: {str(e)}")
            return self._get_default_context()
    
    def _get_similar_cards_context(self, card_data: Dict[str, Any]) -> str:
        """
        Récupère des cards similaires précédemment analysées pour améliorer la décision.
        """
        try:
            # Construire une requête basée sur le nom et la description de la card
            search_text = f"{card_data.get('name', '')} {card_data.get('desc', '')}"
            
            # Rechercher des cards similaires
            results = self.chroma_manager.similarity_search(search_text, k=3)
            
            similar_cards = []
            for result in results:
                # Vérifier si c'est un résultat de card analysée (contient des métadonnées spécifiques)
                if result.get('metadata') and 'criticality_level' in str(result.get('content', '')):
                    similar_cards.append(result['content'])
            
            if similar_cards:
                return "\n\n".join(similar_cards)
            else:
                return "Aucune card similaire trouvée dans l'historique."
                
        except Exception as e:
            current_app.logger.warning(f"Erreur lors de la récupération des cards similaires: {str(e)}")
            return "Historique des cards non disponible."
    
    def _get_default_context(self) -> str:
        """Contexte par défaut si aucun document n'est trouvé."""
        return """
        Cette application est un système de gestion de projets avec analyse intelligente des tâches.
        L'application permet de suivre l'avancement des projets, identifier les blocages,
        et prioriser les tâches selon leur impact business et technique.
        Les critères de criticité incluent l'impact sur les utilisateurs, les délais,
        les dépendances techniques et la valeur business.
        """
    
    def _build_criticality_prompt(self, card_data: Dict[str, Any], app_context: str, similar_cards: str) -> str:
        """
        Génère un prompt détaillé pour évaluer le niveau de criticité d'une carte Trello,
        en tenant compte du contexte applicatif, de l'historique des cartes similaires
        et des impacts potentiels.
        """
        return f'''
You are a Senior Product Owner and certified Risk Analyst with over 15 years of experience in agile SaaS environments. Your mission is to assess the **criticality** of a Trello card in a **healthcare-grade application**. Your assessment must be based on **business impact, user risk, and technical urgency**, considering all available data.

━━━━━━━━━━━━━━━━━━
 APPLICATION CONTEXT:
{app_context}

 SIMILAR CARDS HISTORY:
{similar_cards}

 CARD TO ANALYZE:
- **Title**: {card_data.get('name', 'N/A')}
- **Description**: {card_data.get('desc', 'No description')}
- **Labels**: {', '.join([label.get('name', '') for label in card_data.get('labels', [])]) or 'None'}
- **Due Date**: {card_data.get('due', 'None')}
- **List Name**: {card_data.get('list_name', 'N/A')}
- **Members**: {', '.join([member.get('fullName', '') for member in card_data.get('members', [])]) or 'None'}

━━━━━━━━━━━━━━━━━━
 STEP 1: CONTEXTUAL RELEVANCE CHECK  
If the card is **completely unrelated** to the above application context (no logical or functional connection), respond with **exactly**:
> OUT_OF_CONTEXT

━━━━━━━━━━━━━━━━━━
 STEP 2: CRITICALITY ASSESSMENT  
Evaluate how this card impacts the system's operation, user safety, business workflow, or service reliability.  
Every task must receive a criticality level. **There are no non-critical tasks.**

CRITICALITY LEVELS:
-  **HIGH**: Major disruption to production, sensitive data exposure, decision-critical issues, or direct patient/user harm
-  **MEDIUM**: Significant user or business impact, degraded experience, or operational inefficiencies
-  **LOW**: Minor improvements, cosmetic changes, documentation, or low-risk refactors

━━━━━━━━━━━━━━━━━━
 DECISION LOGIC:
1. Use the application context and card content to infer scope and risk.
2. If necessary, extrapolate the real-world impact.
3. Assign a level: HIGH, MEDIUM, or LOW.
4. Provide a **clear and direct justification** explaining why this level was chosen.

━━━━━━━━━━━━━━━━━━
 FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
Criticality Level: HIGH  
Justification: [One short paragraph, precise, clear, professional. Mention app context, card content, and impact.]

━━━━━━━━━━━━━━━━━━
Now assess this card.
'''


    def analyze_card_criticality(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse la criticité d'une card Trello.
        
        Args:
            card_data: Données de la card à analyser
            
        Returns:
            Résultat de l'analyse avec le niveau de criticité
        """
        try:
            # Récupérer le contexte de l'application depuis les documents uploadés
            app_context = self._get_application_context()
            
            # Vérifier s'il y a des documents uploadés
            if not app_context or app_context.strip() == "" or app_context == self._get_default_context():
                return {
                    'card_id': card_data.get('id'),
                    'card_name': card_data.get('name'),
                    'criticality_level': 'LOW',
                    'justification': "Criticité assignée par défaut (LOW) - Veuillez uploader un document de description pour une analyse plus précise",
                    'analyzed_at': None,
                    'success': True
                }
            
            # Récupérer des cards similaires précédemment analysées
            similar_cards = self._get_similar_cards_context(card_data)
            
            # Construire le prompt avec contexte enrichi
            prompt = self._build_criticality_prompt(card_data, app_context, similar_cards)
            
            # Analyser avec Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text.strip().upper()
            
            # Vérifier d'abord si la card est hors contexte
            if 'OUT_OF_CONTEXT' in response_text:
                return {
                    'card_id': card_data.get('id'),
                    'card_name': card_data.get('name'),
                    'criticality_level': 'OUT_OF_CONTEXT',
                    'justification': "Désolé, je peux vous répondre que selon le contexte de votre document uploadé.",
                    'analyzed_at': None,
                    'success': True
                }
            
            # Parser la réponse - tous les tickets sont critiques avec un niveau
            criticality_level = 'LOW'  # Niveau par défaut
            
            if 'HIGH' in response_text:
                criticality_level = 'HIGH'
            elif 'MEDIUM' in response_text:
                criticality_level = 'MEDIUM'
            elif 'LOW' in response_text:
                criticality_level = 'LOW'
            else:
                # Si aucun niveau n'est détecté, assigner LOW par défaut
                current_app.logger.warning(f"Niveau de criticité non détecté dans la réponse: {response_text}")
                criticality_level = 'LOW'
            
            result = {
                'card_id': card_data.get('id'),
                'card_name': card_data.get('name'),
                'criticality_level': criticality_level,
                'justification': response_text,
                'analyzed_at': None,  # Sera ajouté par la route
                'success': True
            }
            
            # Sauvegarder l'analyse dans ChromaDB pour l'historique
            self._save_analysis_to_history(card_data, result)
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'analyse de criticité: {str(e)}")
            return {
                'card_id': card_data.get('id'),
                'card_name': card_data.get('name'),
                'criticality_level': 'LOW',  # Niveau par défaut en cas d'erreur
                'error': str(e),
                'success': False
            }
    
    def _save_analysis_to_history(self, card_data: Dict[str, Any], analysis_result: Dict[str, Any]):
        """
        Sauvegarde l'analyse dans ChromaDB pour créer un historique.
        """
        try:
            # Créer un document d'historique
            history_text = f"""
CARD ANALYSÉE: {card_data.get('name', 'N/A')}
DESCRIPTION: {card_data.get('desc', 'Aucune')}
LABELS: {', '.join([label.get('name', '') for label in card_data.get('labels', [])])}
RÉSULTAT: {analysis_result['criticality_level']}
BOARD: {card_data.get('board_name', 'N/A')}
            """.strip()
            
            # Métadonnées pour retrouver facilement
            metadata = {
                'type': 'card_analysis',
                'card_id': card_data.get('id'),
                'board_id': card_data.get('board_id'),
                'criticality_level': analysis_result['criticality_level']
            }
            
            # Sauvegarder dans ChromaDB
            self.chroma_manager.store_documents([{
                'content': history_text,
                'metadata': metadata
            }])
            
        except Exception as e:
            current_app.logger.warning(f"Erreur lors de la sauvegarde de l'historique: {str(e)}")
            # Ne pas faire échouer l'analyse si la sauvegarde échoue
