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
                current_app.logger.info(f"Contexte récupéré depuis {len(files_content)} fichiers uploadés")
                return "\n\n".join(context_parts)
            else:
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
        Construit le prompt pour l'analyse de criticité.
        
        Args:
            card_data: Données de la card Trello
            app_context: Contexte de l'application depuis les documents uploadés
            similar_cards: Cards similaires précédemment analysées
            
        Returns:
            Prompt formaté pour Gemini
        """
        return f"""
Tu es un Product Owner expert avec une approche TRÈS SÉVÈRE dans l'analyse de criticité des tâches.

CONTEXTE DE L'APPLICATION (Extrait des fichiers uploadés):
{app_context}

HISTORIQUE DES CARDS SIMILAIRES ANALYSÉES:
{similar_cards}

CARD À ANALYSER:
- Titre: {card_data.get('name', 'N/A')}
- Description: {card_data.get('desc', 'Aucune description')}
- Labels: {', '.join([label.get('name', '') for label in card_data.get('labels', [])])}
- Date d'échéance: {card_data.get('due', 'Aucune')}
- Liste: {card_data.get('list_name', 'N/A')}
- Membres: {', '.join([member.get('fullName', '') for member in card_data.get('members', [])])}

ÉTAPE 1 - VÉRIFICATION DE CONTEXTE:
Si cette card concerne une application différente ou un projet sans rapport avec le contexte fourni, réponds EXACTEMENT: "HORS_CONTEXTE"

ÉTAPE 2 - ANALYSE DE CRITICITÉ (APPROCHE TRÈS SÉVÈRE):
Une tâche est considérée comme CRITIQUE uniquement si elle répond à UN ou PLUSIEURS de ces critères STRICTS:

🔴 CRITÈRES CRITIQUES ABSOLUS:
- L'application ou une fonctionnalité PRINCIPALE devient inutilisable
- Perte ou corruption de données importantes
- Faille de sécurité ou exposition de données sensibles
- Impact financier direct et immédiat (perte de revenus)
- Non-respect de réglementations critiques
- Application en panne ou inaccessible en production

❌ NE SONT GÉNÉRALEMENT PAS CRITIQUES (sauf exception majeure):
- Améliorations esthétiques (design, couleurs, logos)
- Optimisations de performance mineures
- Documentation et guides utilisateur
- Nouvelles fonctionnalités (même importantes)
- Corrections de bugs mineurs sans impact majeur
- Tâches de maintenance préventive
- Refactoring et nettoyage de code

ÉTAPE 3 - NIVEAUX DE CRITICITÉ (uniquement si critique):
- HIGH: Impact immédiat sur l'utilisation en production
- MEDIUM: Fonctionnalité importante affectée mais contournement possible
- LOW: Impact limité mais nécessite correction

PROCESSUS DE DÉCISION EN 2 ÉTAPES:
1. Cette tâche empêche-t-elle le bon fonctionnement PRINCIPAL de l'application ? OUI/NON
2. Si OUI, quel est le niveau d'impact ? HIGH/MEDIUM/LOW

IMPORTANT: Sois TRÈS SÉLECTIF. La majorité des tâches (80-90%) ne sont PAS critiques.

FORMAT DE RÉPONSE OBLIGATOIRE:
- "HORS_CONTEXTE" si hors contexte
- "NON" si pas critique (cas le plus fréquent)
- "OUI HIGH" si critique impact majeur
- "OUI MEDIUM" si critique impact modéré
- "OUI LOW" si critique impact limité

Analyse maintenant cette card:
"""

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
                    'is_critical': False,
                    'criticality_level': 'NO_CONTEXT',
                    'raw_response': "Veuillez uploader un document de description",
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
            if 'HORS_CONTEXTE' in response_text or 'HORS CONTEXTE' in response_text:
                return {
                    'card_id': card_data.get('id'),
                    'card_name': card_data.get('name'),
                    'is_critical': False,
                    'criticality_level': 'HORS_CONTEXTE',
                    'raw_response': "Désolé, je peux vous répondre que selon le contexte de votre document uploadé.",
                    'analyzed_at': None,
                    'success': True
                }
            
            # Parser la réponse OUI/NON + niveau
            is_critical = False
            criticality_level = 'NON'
            
            if response_text.startswith('OUI'):
                is_critical = True
                if 'HIGH' in response_text:
                    criticality_level = 'HIGH'
                elif 'MEDIUM' in response_text:
                    criticality_level = 'MEDIUM'
                elif 'LOW' in response_text:
                    criticality_level = 'LOW'
                else:
                    # Si OUI mais pas de niveau spécifié, par défaut MEDIUM
                    criticality_level = 'MEDIUM'
            elif response_text == 'NON':
                is_critical = False
                criticality_level = 'NON'
            else:
                # Fallback pour réponses inattendues
                current_app.logger.warning(f"Réponse inattendue de Gemini: {response_text}")
                # Essayer de parser quand même
                if any(level in response_text for level in ['HIGH', 'MEDIUM', 'LOW']):
                    is_critical = True
                    if 'HIGH' in response_text:
                        criticality_level = 'HIGH'
                    elif 'MEDIUM' in response_text:
                        criticality_level = 'MEDIUM'
                    else:
                        criticality_level = 'LOW'
                else:
                    is_critical = False
                    criticality_level = 'NON'
            
            result = {
                'card_id': card_data.get('id'),
                'card_name': card_data.get('name'),
                'is_critical': is_critical,
                'criticality_level': criticality_level,
                'raw_response': response_text,
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
                'is_critical': False,
                'criticality_level': 'NON',  # Valeur par défaut en cas d'erreur
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
CRITIQUE: {'OUI' if analysis_result['is_critical'] else 'NON'}
BOARD: {card_data.get('board_name', 'N/A')}
            """.strip()
            
            # Métadonnées pour retrouver facilement
            metadata = {
                'type': 'card_analysis',
                'card_id': card_data.get('id'),
                'board_id': card_data.get('board_id'),
                'criticality_level': analysis_result['criticality_level'],
                'is_critical': analysis_result['is_critical']
            }
            
            # Sauvegarder dans ChromaDB
            self.chroma_manager.store_documents([{
                'content': history_text,
                'metadata': metadata
            }])
            
        except Exception as e:
            current_app.logger.warning(f"Erreur lors de la sauvegarde de l'historique: {str(e)}")
            # Ne pas faire échouer l'analyse si la sauvegarde échoue
