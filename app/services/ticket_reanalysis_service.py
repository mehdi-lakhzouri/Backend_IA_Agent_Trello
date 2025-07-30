"""
Service de réanalyse d'un ticket spécifique Trello.
Ce service permet de réanalyser un ticket existant en créant une nouvelle analyse 
et analyse_board tout en prenant en compte la table config.
"""

from datetime import datetime
from typing import Dict, Any, Optional
import requests
import os
from flask import current_app

from app import db
from app.models.trello_models import (
    Config, Analyse, AnalyseBoard, Tickets, 
    TrelloCard, CriticalityAnalysis
)
from app.services.criticality_analyzer import CriticalityAnalyzer


class TicketReanalysisService:
    """Service pour réanalyser un ticket spécifique."""
    
    def __init__(self):
        """Initialise le service de réanalyse."""
        self.analyzer = CriticalityAnalyzer()
    
    def reanalyze_ticket(self, trello_ticket_id: str, config_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Réanalyse un ticket spécifique en créant une nouvelle analyse et analyse_board.
        
        Args:
            trello_ticket_id (str): ID du ticket Trello à réanalyser
            config_id (int, optional): ID de la configuration à utiliser. 
                                     Si None, utilise la dernière configuration.
        
        Returns:
            Dict[str, Any]: Résultat de la réanalyse incluant les détails de l'analyse
        """
        try:
            # 1. Récupérer la configuration
            config = self._get_config(config_id)
            if not config:
                return {
                    "success": False,
                    "error": "Aucune configuration trouvée",
                    "error_code": "NO_CONFIG"
                }
            
            # 2. Récupérer les données du ticket depuis Trello
            ticket_data = self._fetch_ticket_from_trello(trello_ticket_id, config)
            if not ticket_data.get('success'):
                return ticket_data
            
            # 3. Créer une nouvelle analyse
            analysis = self._create_new_analysis(trello_ticket_id)
            
            # 4. Créer une nouvelle analyse_board
            analysis_board = self._create_analysis_board(analysis.analyse_id, config)
            
            # 5. Analyser le ticket avec l'AI
            criticality_result = self._analyze_ticket_criticality(ticket_data['card_data'])
            
            # 6. Sauvegarder le ticket réanalysé
            ticket_record = self._save_reanalyzed_ticket(
                analysis_board.id, 
                trello_ticket_id, 
                ticket_data['card_data'], 
                criticality_result
            )
            
            # 7. Commit de toutes les modifications
            db.session.commit()
            
            return {
                "success": True,
                "analysis": {
                    "analyse_id": analysis.analyse_id,
                    "reference": analysis.reference,
                    "created_at": analysis.createdAt.isoformat()
                },
                "analysis_board": {
                    "id": analysis_board.id,
                    "platform": analysis_board.platform,
                    "board_info": analysis_board.get_board_info_from_config(config.id)
                },
                "ticket": {
                    "id_ticket": ticket_record.id_ticket,
                    "trello_ticket_id": ticket_record.trello_ticket_id,
                    "criticality_level": ticket_record.criticality_level,
                    "created_at": ticket_record.createdAt.isoformat()
                },
                "criticality_analysis": criticality_result,
                "config_used": {
                    "config_id": config.id,
                    "board_id": config.config_data.get('boardId'),
                    "board_name": config.config_data.get('boardName'),
                    "list_id": config.config_data.get('listId'),
                    "list_name": config.config_data.get('listName')
                }
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erreur lors de la réanalyse du ticket {trello_ticket_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Erreur lors de la réanalyse: {str(e)}",
                "error_code": "REANALYSIS_ERROR"
            }
    
    def _get_config(self, config_id: Optional[int] = None) -> Optional[Config]:
        """
        Récupère la configuration à utiliser.
        
        Args:
            config_id (int, optional): ID de la configuration spécifique
        
        Returns:
            Optional[Config]: Configuration trouvée ou None
        """
        if config_id:
            return Config.query.get(config_id)
        else:
            return Config.get_latest_config()
    
    def _fetch_ticket_from_trello(self, trello_ticket_id: str, config: Config) -> Dict[str, Any]:
        """
        Récupère les données du ticket depuis l'API Trello.
        
        Args:
            trello_ticket_id (str): ID du ticket Trello
            config (Config): Configuration contenant le token et les infos du board
        
        Returns:
            Dict[str, Any]: Données du ticket ou erreur
        """
        try:
            # Construire l'URL de l'API Trello
            card_url = f"https://api.trello.com/1/cards/{trello_ticket_id}"
            
            # Récupérer le token depuis la config (déchiffré)
            token = config.config_data.get('token')
            if not token:
                return {
                    "success": False,
                    "error": "Token Trello non trouvé dans la configuration",
                    "error_code": "NO_TOKEN"
                }
            
            # Paramètres de l'API
            params = {
                'key': os.environ.get('TRELLO_API_KEY'),
                'token': token,
                'fields': 'id,name,desc,due,url,dateLastActivity,idList',
                'attachments': 'false',
                'members': 'true',
                'labels': 'true'
            }
            
            # Faire l'appel API
            response = requests.get(card_url, params=params, timeout=30)
            response.raise_for_status()
            card_data = response.json()
            
            # Enrichir avec les informations de configuration
            enriched_card_data = {
                'id': card_data['id'],
                'name': card_data['name'],
                'desc': card_data.get('desc', ''),
                'due': card_data.get('due'),
                'list_name': config.config_data.get('listName', 'Liste inconnue'),
                'board_id': config.config_data.get('boardId'),
                'board_name': config.config_data.get('boardName', 'Board inconnu'),
                'labels': card_data.get('labels', []),
                'members': card_data.get('members', []),
                'url': card_data['url'],
                'idList': card_data.get('idList'),
                'dateLastActivity': card_data.get('dateLastActivity')
            }
            
            return {
                "success": True,
                "card_data": enriched_card_data
            }
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Erreur API Trello pour le ticket {trello_ticket_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Erreur lors de la récupération du ticket: {str(e)}",
                "error_code": "TRELLO_API_ERROR"
            }
        except Exception as e:
            current_app.logger.error(f"Erreur inattendue lors de la récupération du ticket {trello_ticket_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Erreur inattendue: {str(e)}",
                "error_code": "UNEXPECTED_ERROR"
            }
    
    def _create_new_analysis(self, trello_ticket_id: str) -> Analyse:
        """
        Crée une nouvelle analyse pour la réanalyse.
        
        Args:
            trello_ticket_id (str): ID du ticket pour générer une référence unique
        
        Returns:
            Analyse: Nouvelle analyse créée
        """
        # Générer une référence unique pour la réanalyse
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        reference = f"reanalysis_{trello_ticket_id}_{timestamp}"
        
        analysis = Analyse(reference=reference)
        db.session.add(analysis)
        db.session.flush()  # Pour récupérer l'ID
        
        current_app.logger.info(f"Nouvelle analyse créée: {reference} (ID: {analysis.analyse_id})")
        return analysis
    
    def _create_analysis_board(self, analyse_id: int, config: Config) -> AnalyseBoard:
        """
        Crée une nouvelle analyse_board.
        
        Args:
            analyse_id (int): ID de l'analyse parent
            config (Config): Configuration pour déterminer la plateforme
        
        Returns:
            AnalyseBoard: Nouvelle analyse_board créée
        """
        analysis_board = AnalyseBoard(
            analyse_id=analyse_id,
            platform="Trello"  # Platform fixe pour Trello
        )
        
        db.session.add(analysis_board)
        db.session.flush()  # Pour récupérer l'ID
        
        current_app.logger.info(f"Nouvelle analyse_board créée: ID {analysis_board.id} pour analyse {analyse_id}")
        return analysis_board
    
    def _analyze_ticket_criticality(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse la criticité du ticket avec l'AI.
        
        Args:
            card_data (Dict[str, Any]): Données du ticket à analyser
        
        Returns:
            Dict[str, Any]: Résultat de l'analyse de criticité
        """
        try:
            result = self.analyzer.analyze_card_criticality(card_data)
            result['reanalyzed_at'] = datetime.utcnow().isoformat()
            return result
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'analyse de criticité: {str(e)}")
            return {
                "success": False,
                "error": f"Erreur lors de l'analyse IA: {str(e)}",
                "card_id": card_data.get('id'),
                "card_name": card_data.get('name'),
                "reanalyzed_at": datetime.utcnow().isoformat()
            }
    
    def _save_reanalyzed_ticket(self, analyse_board_id: int, trello_ticket_id: str, 
                               card_data: Dict[str, Any], criticality_result: Dict[str, Any]) -> Tickets:
        """
        Sauvegarde le ticket réanalysé dans la base de données.
        
        Args:
            analyse_board_id (int): ID de l'analyse_board
            trello_ticket_id (str): ID du ticket Trello
            card_data (Dict[str, Any]): Données du ticket
            criticality_result (Dict[str, Any]): Résultat de l'analyse de criticité
        
        Returns:
            Tickets: Ticket sauvegardé
        """
        # Construire les métadonnées du ticket
        ticket_metadata = {
            'name': card_data.get('name'),
            'desc': card_data.get('desc', ''),
            'due': card_data.get('due'),
            'url': card_data.get('url'),
            'labels': card_data.get('labels', []),
            'members': card_data.get('members', []),
            'idList': card_data.get('idList'),
            'dateLastActivity': card_data.get('dateLastActivity'),
            'analysis_result': criticality_result,
            'reanalyzed': True,
            'reanalysis_timestamp': datetime.utcnow().isoformat()
        }
        
        # Déterminer le niveau de criticité
        criticality_level = None
        if criticality_result.get('success') and criticality_result.get('criticality_level'):
            criticality_level = criticality_result['criticality_level'].lower()
        
        # Créer le nouveau ticket (même si un existe déjà, pour garder l'historique)
        ticket = Tickets(
            analyse_board_id=analyse_board_id,
            trello_ticket_id=trello_ticket_id,
            ticket_metadata=ticket_metadata,
            criticality_level=criticality_level
        )
        
        db.session.add(ticket)
        db.session.flush()  # Pour récupérer l'ID
        
        current_app.logger.info(f"Ticket réanalysé sauvegardé: {ticket.id_ticket} pour Trello ID {trello_ticket_id}")
        return ticket
    
    def get_ticket_reanalysis_history(self, trello_ticket_id: str) -> Dict[str, Any]:
        """
        Récupère l'historique des réanalyses d'un ticket.
        
        Args:
            trello_ticket_id (str): ID du ticket Trello
        
        Returns:
            Dict[str, Any]: Historique des réanalyses
        """
        try:
            # Récupérer tous les tickets avec cet ID Trello
            tickets = Tickets.query.filter_by(trello_ticket_id=trello_ticket_id)\
                           .order_by(Tickets.createdAt.desc()).all()
            
            if not tickets:
                return {
                    "success": False,
                    "error": "Aucune analyse trouvée pour ce ticket",
                    "trello_ticket_id": trello_ticket_id
                }
            
            # Construire l'historique
            history = []
            for ticket in tickets:
                # Récupérer les informations de l'analyse et analyse_board
                analyse_board = AnalyseBoard.query.get(ticket.analyse_board_id)
                analyse = Analyse.query.get(analyse_board.analyse_id) if analyse_board else None
                
                history_entry = {
                    "id_ticket": ticket.id_ticket,
                    "criticality_level": ticket.criticality_level,
                    "created_at": ticket.createdAt.isoformat(),
                    "updated_at": ticket.updatedAt.isoformat(),
                    "is_reanalysis": ticket.ticket_metadata.get('reanalyzed', False),
                    "analysis_reference": analyse.reference if analyse else None,
                    "analysis_id": analyse.analyse_id if analyse else None,
                    "analyse_board_id": ticket.analyse_board_id,
                    "board_info": analyse_board.get_board_info_from_config() if analyse_board else None
                }
                
                # Ajouter les détails de l'analyse si disponibles
                analysis_result = ticket.ticket_metadata.get('analysis_result', {})
                if analysis_result:
                    history_entry["analysis_details"] = {
                        "success": analysis_result.get('success'),
                        "reasoning": analysis_result.get('reasoning'),
                        "confidence": analysis_result.get('confidence'),
                        "analyzed_at": analysis_result.get('analyzed_at') or analysis_result.get('reanalyzed_at')
                    }
                
                history.append(history_entry)
            
            return {
                "success": True,
                "trello_ticket_id": trello_ticket_id,
                "total_analyses": len(history),
                "latest_analysis": history[0] if history else None,
                "history": history
            }
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération de l'historique pour {trello_ticket_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Erreur lors de la récupération de l'historique: {str(e)}",
                "trello_ticket_id": trello_ticket_id
            }
