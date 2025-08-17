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
    """Analyse la criticité des cards Trello en utilisant Gemini 2.5 Flash."""
    
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
You are a Senior Product Owner and certified Risk Analyst with over 15 years of experience in agile SaaS environments. Your mission is to assess the **criticality** of a Trello card . Your assessment must be based on **business impact, user risk, and technical urgency**, considering all available data.

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
1. Use the application context and use it in an efficient manner with card content to infer scope and risk.
2. If necessary, extrapolate the real-world impact.
3. Assign a level: HIGH, MEDIUM, or LOW.
4. Provide a **clear and direct justification maximum 3-5 sentences** explaining why this level was chosen .

━━━━━━━━━━━━━━━━━━
 FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
Criticality Level: HIGH  
Justification: [One short paragraph, precise, clear, professional. Mention app context, card content, and impact.]

━━━━━━━━━━━━━━━━━━
Now assess this card.
'''


    def _build_reanalysis_prompt(self, card_data: Dict[str, Any], app_context: str, similar_cards: str, previous_analysis: Dict[str, Any]) -> str:
        """
        Génère un prompt spécialisé pour la réanalyse avec vérification approfondie.
        """
        previous_level = previous_analysis.get('criticality_level', 'UNKNOWN')
        previous_justification = previous_analysis.get('justification', 'No previous justification')
        
        return f'''
You are a Senior Product Owner and Risk Assessment Specialist conducting a **DETAILED RE-ANALYSIS** of a previously evaluated Trello card. Your goal is to perform a thorough verification of the criticality level with enhanced scrutiny and provide a clear, concise justification in English.

━━━━━━━━━━━━━━━━━━
 APPLICATION CONTEXT:
{app_context}

 SIMILAR CARDS HISTORY:
{similar_cards}

 CARD UNDER RE-ANALYSIS:
- **Title**: {card_data.get('name', 'N/A')}
- **Description**: {card_data.get('desc', 'No description')}
- **Labels**: {', '.join([label.get('name', '') for label in card_data.get('labels', [])]) or 'None'}
- **Due Date**: {card_data.get('due', 'None')}
- **List Name**: {card_data.get('list_name', 'N/A')}
- **Members**: {', '.join([member.get('fullName', '') for member in card_data.get('members', [])]) or 'None'}

 PREVIOUS ANALYSIS:
- **Previous Level**: {previous_level}
- **Previous Justification**: {previous_justification}

━━━━━━━━━━━━━━━━━━
 RE-ANALYSIS METHODOLOGY:
1. **DEEPER CONTEXT ANALYSIS**: Re-examine the card against the application context with more granular detail
2. **IMPACT VERIFICATION**: Cross-check business impact, user experience, and technical risks
3. **DEPENDENCY ASSESSMENT**: Consider downstream effects and interconnected systems
4. **TIMELINE URGENCY**: Evaluate time-sensitive implications and priority conflicts
5. **VALIDATION**: Compare with previous assessment and justify any changes or confirmations

 ENHANCED CRITICALITY FRAMEWORK:
- **HIGH**: Production-critical issues, data security risks, user safety concerns, revenue-impacting problems, or system-wide failures
- **MEDIUM**: Significant workflow disruptions, performance degradation, user experience issues, or moderate business impact
- **LOW**: Minor improvements, documentation, UI polish, or low-impact optimizations

━━━━━━━━━━━━━━━━━━
 DELIVERABLE:
Provide a **CONCISE, PROFESSIONAL JUSTIFICATION** (3-4 sentences maximum) in English that:
- Clearly states the confirmed or revised criticality level
- Explains the key factors that drive this assessment
- References specific aspects of the application context
- Mentions any changes from the previous analysis (if applicable)

 FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
CRITICALITY LEVEL: [HIGH/MEDIUM/LOW]
JUSTIFICATION: [3-4 sentences explaining the assessment in clear, professional English]

━━━━━━━━━━━━━━━━━━
Proceed with the detailed re-analysis now.
'''

    def reanalyze_card_criticality(self, card_data: Dict[str, Any], previous_analysis: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Effectue une réanalyse approfondie de la criticité d'une card avec vérification renforcée.
        
        Args:
            card_data: Données de la card à réanalyser
            previous_analysis: Résultat de l'analyse précédente pour comparaison
            
        Returns:
            Résultat de la réanalyse avec justification courte et claire
        """
        try:
            # Récupérer le contexte de l'application
            app_context = self._get_application_context()
            
            if not app_context or app_context.strip() == "" or app_context == self._get_default_context():
                return {
                    'card_id': card_data.get('id'),
                    'card_name': card_data.get('name'),
                    'criticality_level': 'LOW',
                    'justification': "Default LOW criticality assigned - Please upload application documentation for more accurate analysis",
                    'analyzed_at': None,
                    'success': True,
                    'is_reanalysis': True
                }
            
            # Récupérer des cards similaires
            similar_cards = self._get_similar_cards_context(card_data)
            
            # Construire le prompt de réanalyse spécialisé
            prompt = self._build_reanalysis_prompt(card_data, app_context, similar_cards, previous_analysis or {})
            
            # Analyser avec Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parser la réponse pour extraire le niveau et la justification
            criticality_level = 'LOW'  # Niveau par défaut
            justification = response_text
            
            # Extraire le niveau de criticité
            response_upper = response_text.upper()
            if 'CRITICALITY LEVEL: HIGH' in response_upper or 'HIGH' in response_upper.split('\n')[0]:
                criticality_level = 'HIGH'
            elif 'CRITICALITY LEVEL: MEDIUM' in response_upper or 'MEDIUM' in response_upper.split('\n')[0]:
                criticality_level = 'MEDIUM'
            elif 'CRITICALITY LEVEL: LOW' in response_upper or 'LOW' in response_upper.split('\n')[0]:
                criticality_level = 'LOW'
            
            # Extraire la justification (partie après "JUSTIFICATION:")
            lines = response_text.split('\n')
            justification_lines = []
            capture_justification = False
            
            for line in lines:
                if 'JUSTIFICATION:' in line.upper():
                    # Prendre le texte après "JUSTIFICATION:" sur la même ligne
                    justification_part = line.split(':', 1)
                    if len(justification_part) > 1:
                        justification_lines.append(justification_part[1].strip())
                    capture_justification = True
                elif capture_justification and line.strip():
                    justification_lines.append(line.strip())
            
            if justification_lines:
                justification = ' '.join(justification_lines)
            else:
                # Fallback: utiliser toute la réponse si la structure n'est pas respectée
                justification = response_text
            
            # Sauvegarder dans ChromaDB pour enrichir l'historique
            try:
                card_analysis_text = f"""
                Card: {card_data.get('name', 'Unknown')}
                Criticality: {criticality_level}
                Analysis: {justification}
                Context: Re-analysis
                """
                
                self.chroma_manager.add_documents(
                    documents=[card_analysis_text],
                    metadatas=[{
                        'card_id': card_data.get('id'),
                        'card_name': card_data.get('name'),
                        'type': 'card_reanalysis',
                        'criticality_level': criticality_level
                    }]
                )
            except Exception as e:
                current_app.logger.warning(f"Erreur lors de la sauvegarde dans ChromaDB: {str(e)}")
            
            return {
                'card_id': card_data.get('id'),
                'card_name': card_data.get('name'),
                'criticality_level': criticality_level,
                'justification': justification,
                'analyzed_at': None,
                'success': True,
                'is_reanalysis': True
            }
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la réanalyse de criticité: {str(e)}")
            return {
                'card_id': card_data.get('id'),
                'card_name': card_data.get('name'),
                'criticality_level': 'LOW',
                'justification': f"Re-analysis failed due to technical error: {str(e)}. Assigned LOW criticality as fallback.",
                'analyzed_at': None,
                'success': False,
                'error': str(e),
                'is_reanalysis': True
            }

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

    # =============================
    # Batch analysis optimisation
    # =============================
    def analyze_cards_batch(self, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyse plusieurs cards en un seul appel LLM pour optimiser latence & coût.

        Stratégie:
        - Récupère le contexte applicatif une seule fois.
        - Construit un prompt listant les cartes sous forme JSON minimale.
        - Demande un retour STRICTEMENT en JSON (liste d'objets) avec: id, criticality_level (HIGH|MEDIUM|LOW|OUT_OF_CONTEXT), justification.
        - Si parsing échoue: fallback vers analyse unitaire.
        """
        results: List[Dict[str, Any]] = []
        if not cards:
            return results
        try:
            app_context = self._get_application_context()
            # Si pas de contexte, appliquer fallback LOW
            if not app_context or app_context.strip() == "" or app_context == self._get_default_context():
                for c in cards:
                    results.append({
                        'card_id': c.get('id'),
                        'card_name': c.get('name'),
                        'criticality_level': 'LOW',
                        'justification': "Criticité assignée par défaut (LOW) - Veuillez uploader un document de description pour une analyse plus précise",
                        'analyzed_at': None,
                        'success': True
                    })
                return results

            # Préparer liste de cartes condensée
            def _short(text: str, limit: int = 400):
                if not text:
                    return ''
                t = text.strip().replace('\n', ' ')
                return (t[:limit] + '…') if len(t) > limit else t

            cards_spec = []
            for c in cards:
                cards_spec.append({
                    'id': c.get('id'),
                    'name': c.get('name'),
                    'desc': _short(c.get('desc', '')),
                    'due': c.get('due'),
                    'list_name': c.get('list_name'),
                    'labels': [lbl.get('name') for lbl in c.get('labels', [])],
                    'members': [m.get('fullName') for m in c.get('members', [])]
                })

            prompt = f"""
You are a senior product owner risk analyst. You will receive an APPLICATION CONTEXT and a LIST OF TREllo CARDS in JSON.
Return ONLY a JSON array. Each element MUST contain:
  id: original card id
  criticality_level: one of HIGH, MEDIUM, LOW, or OUT_OF_CONTEXT (if unrelated to context)
  justification: 1 short paragraph (max 3 sentences) in French. If OUT_OF_CONTEXT specify politely it's outside provided context.
Rules:
- Every in-context card must be HIGH / MEDIUM / LOW (no other value)
- Be concise, no markdown, no extra commentary outside the JSON
APPLICATION CONTEXT:\n{app_context[:4000]}\n
CARDS_JSON = {json.dumps(cards_spec, ensure_ascii=False)}

Return ONLY the JSON array (no explanation outside JSON).
"""
            response = self.model.generate_content(prompt)
            raw_text = (response.text or '').strip()
            # Isolate JSON array
            if '[' not in raw_text:
                raise ValueError('Réponse batch sans JSON array')
            json_segment = raw_text[raw_text.index('['): raw_text.rindex(']') + 1]
            try:
                parsed = json.loads(json_segment)
            except Exception as parse_err:  # noqa: BLE001
                raise ValueError(f"Parsing JSON batch échoué: {parse_err}") from parse_err
            # Map results by id for safety
            by_id = {str(r.get('id')): r for r in parsed if isinstance(r, dict) and r.get('id')}
            for c in cards:
                cid = str(c.get('id'))
                p = by_id.get(cid)
                if not p:
                    # Fallback single analyse
                    single = self.analyze_card_criticality(c)
                    results.append(single)
                    continue
                lvl = (p.get('criticality_level') or p.get('criticality') or '').upper()
                if lvl not in {'HIGH','MEDIUM','LOW','OUT_OF_CONTEXT'}:
                    # Try detect keywords
                    txt = json.dumps(p).upper()
                    if 'HIGH' in txt:
                        lvl = 'HIGH'
                    elif 'MEDIUM' in txt:
                        lvl = 'MEDIUM'
                    elif 'LOW' in txt:
                        lvl = 'LOW'
                    else:
                        lvl = 'LOW'
                justification = p.get('justification') or p.get('reason') or ''
                results.append({
                    'card_id': cid,
                    'card_name': c.get('name'),
                    'criticality_level': lvl,
                    'justification': justification,
                    'analyzed_at': None,
                    'success': True
                })
            return results
        except Exception as e:  # noqa: BLE001
            # Fallback: analyse unitaire pour chaque card
            from flask import current_app
            current_app.logger.warning(f"Batch analysis failed, fallback single: {e}")
            for c in cards:
                results.append(self.analyze_card_criticality(c))
            return results
    
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
