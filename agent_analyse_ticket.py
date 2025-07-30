#!/usr/bin/env python3
"""
Agent d'analyse d'un ticket Trello spécifique.

Ce script analyse un ticket Trello unique et crée une session d'analyse
dédiée dans la table 'analyse' avec le ticket analysé dans la table 'tickets'.
"""

import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from logging.handlers import RotatingFileHandler

# Ajouter le répertoire racine au path pour les imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.trello_models import Analyse, AnalyseBoard, Tickets


def setup_logging() -> logging.Logger:
    """
    Configure le système de logging avec rotation des fichiers.
    """
    # Créer le répertoire logs s'il n'existe pas
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Nom du fichier de log basé sur la date
    log_filename = f"agent_analyse_ticket_{datetime.now().strftime('%Y%m%d')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    
    # Configuration du logger
    logger = logging.getLogger('agent_analyse_ticket')
    logger.setLevel(logging.DEBUG)
    
    # Éviter les doublons de handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Handler pour fichier avec rotation (max 10MB, 5 fichiers)
    file_handler = RotatingFileHandler(
        log_filepath, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Handler pour console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Format des logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Initialiser le logger global
logger = setup_logging()


def generate_unique_ticket_reference(card_name: str, board_name: str, card_id: str, existing_info: Dict[str, Any]) -> str:
    """
    Génère une référence unique pour l'analyse d'un ticket.
    Format: ANALYSE_TICKET_[NOUVELLE|REANALYSE]-YYYYMMDD-XXX-[BOARD_NAME]-[CARD_ID]-[CARD_NAME]
    Pour les réanalyses, inclut l'ID du ticket original pour traçabilité
    """
    today = datetime.now().strftime('%Y%m%d')
    
    # Compter les analyses de tickets créées aujourd'hui
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_analyses = Analyse.query.filter(
        Analyse.createdAt >= today_start,
        Analyse.reference.like('ANALYSE_TICKET_%')
    ).count()
    
    # Incrémenter le compteur
    counter = today_analyses + 1
    
    # Nettoyer le nom du board (max 15 caractères)
    board_short_name = ''.join(c for c in board_name if c.isalnum() or c in ' -_')
    board_short_name = board_short_name.replace(' ', '-')[:15].upper()
    
    # Créer un nom court basé sur le nom de la carte (max 15 caractères)
    card_short_name = ''.join(c for c in card_name if c.isalnum() or c in ' -_')
    card_short_name = card_short_name.replace(' ', '-')[:15].upper()
    
    # Vérifier si ce ticket a déjà été analysé (pour indiquer REANALYSE)
    is_reanalysis = existing_info.get('exists', False)
    reanalyse_suffix = "REANALYSE" if is_reanalysis else "NOUVELLE"
    
    # Construire la référence avec l'ID du ticket pour traçabilité
    if is_reanalysis:
        # Pour les réanalyses, inclure l'ID du ticket original
        previous_ticket_id = existing_info.get('previous_ticket_id', 'UNKNOWN')
        reference = f"ANALYSE_TICKET_{reanalyse_suffix}-{today}-{counter:03d}-{board_short_name}-TKT{previous_ticket_id}-{card_id}-{card_short_name}"
        logger.info(f"🔄 RÉANALYSE - Ticket original ID: {previous_ticket_id}")
    else:
        # Pour les nouvelles analyses
        reference = f"ANALYSE_TICKET_{reanalyse_suffix}-{today}-{counter:03d}-{board_short_name}-{card_id}-{card_short_name}"
    
    logger.debug(f"Référence unique générée: {reference}")
    logger.info(f"Format: {reanalyse_suffix} - Board: {board_name} - Card: {card_id}")
    
    return reference


def check_existing_ticket_analysis(card_id: str) -> Dict[str, Any]:
    """
    Vérifie si ce ticket a déjà été analysé et retourne les informations complètes.
    Récupère TOUS les tickets analysés pour ce card_id pour un historique complet.
    """
    try:
        # Chercher tous les tickets avec ce card_id (original + réanalyses)
        existing_tickets = Tickets.query.filter(
            Tickets.trello_ticket_id.like(f'{card_id}%')
        ).order_by(Tickets.createdAt.desc()).all()
        
        if existing_tickets:
            # Prendre le ticket le plus récent comme référence
            latest_ticket = existing_tickets[0]
            
            # Récupérer l'analyse associée au ticket le plus récent
            analyse_board = db.session.get(AnalyseBoard, latest_ticket.analyse_board_id)
            analyse = None
            if analyse_board:
                analyse = db.session.get(Analyse, analyse_board.analyse_id)
            
            logger.info(f"🔍 TICKET DÉJÀ ANALYSÉ TROUVÉ:")
            logger.info(f"   - Nombre total d'analyses: {len(existing_tickets)}")
            logger.info(f"   - Ticket ID le plus récent: {latest_ticket.id_ticket}")
            logger.info(f"   - Analyse précédente: {analyse.reference if analyse else 'N/A'}")
            logger.info(f"   - Date précédente: {latest_ticket.createdAt}")
            logger.info(f"   - Criticité précédente: {latest_ticket.criticality_level}")
            
            # Afficher l'historique complet
            if len(existing_tickets) > 1:
                logger.info(f"📚 HISTORIQUE COMPLET ({len(existing_tickets)} analyses):")
                for i, ticket in enumerate(existing_tickets, 1):
                    ticket_board = db.session.get(AnalyseBoard, ticket.analyse_board_id)
                    ticket_analyse = None
                    if ticket_board:
                        ticket_analyse = db.session.get(Analyse, ticket_board.analyse_id)
                    
                    logger.info(f"   {i}. ID: {ticket.id_ticket} | "
                              f"Ref: {ticket_analyse.reference if ticket_analyse else 'N/A'} | "
                              f"Date: {ticket.createdAt.strftime('%Y-%m-%d %H:%M') if ticket.createdAt else 'N/A'} | "
                              f"Criticité: {ticket.criticality_level}")
            
            return {
                'exists': True,
                'previous_ticket_id': latest_ticket.id_ticket,
                'previous_reference': analyse.reference if analyse else 'N/A',
                'previous_date': latest_ticket.createdAt.isoformat() if latest_ticket.createdAt else None,
                'previous_criticality': latest_ticket.criticality_level,
                'total_analyses': len(existing_tickets),
                'all_tickets': [
                    {
                        'id': t.id_ticket,
                        'date': t.createdAt.isoformat() if t.createdAt else None,
                        'criticality': t.criticality_level
                    } for t in existing_tickets
                ]
            }
        
        logger.info("✨ NOUVEAU TICKET - Première analyse")
        return {'exists': False, 'total_analyses': 0}
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du ticket existant: {str(e)}")
        return {'exists': False, 'total_analyses': 0}


def check_flask_server_running() -> bool:
    """
    Vérifie si le serveur Flask est en cours d'exécution.
    """
    try:
        logger.debug("Vérification de l'état du serveur Flask...")
        response = requests.get("http://localhost:5000/api/trello/config-board-subscription", timeout=5)
        is_running = response.status_code in [200, 404]
        
        if is_running:
            logger.info("Serveur Flask détecté et opérationnel")
        else:
            logger.warning(f"Serveur Flask non disponible (statut: {response.status_code})")
            
        return is_running
    except requests.exceptions.RequestException as e:
        logger.warning(f"Serveur Flask non disponible: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du serveur Flask: {str(e)}")
        return False


def create_ticket_analyse_session(card_name: str, board_name: str, card_id: str, existing_info: Dict[str, Any]) -> Analyse:
    """
    Crée une session d'analyse dédiée pour un ticket spécifique.
    """
    try:
        # Générer une référence unique pour ce ticket
        reference = generate_unique_ticket_reference(card_name, board_name, card_id, existing_info)
        
        logger.info(f"Création d'une session d'analyse pour le ticket: {card_name}")
        logger.info(f"Board: {board_name}")
        logger.info(f"Référence: {reference}")
        
        # Créer la session d'analyse
        analyse = Analyse(
            reference=reference,
            createdAt=datetime.now()
        )
        
        # Sauvegarder en base
        db.session.add(analyse)
        db.session.commit()
        
        logger.info(f"Session d'analyse créée avec succès: ID {analyse.analyse_id}")
        
        return analyse
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la session d'analyse: {str(e)}")
        db.session.rollback()
        raise e


def create_analyse_board_for_ticket(analyse: Analyse, board_id: str, board_name: str) -> AnalyseBoard:
    """
    Crée une entrée analyse_board pour le ticket analysé.
    """
    try:
        logger.debug(f"Création analyse_board pour board: {board_name}")
        
        analyse_board = AnalyseBoard(
            analyse_id=analyse.analyse_id,
            platform='trello',
            createdAt=datetime.now()
        )
        
        # Sauvegarder en base
        db.session.add(analyse_board)
        db.session.commit()
        
        logger.info(f"Analyse board créée: ID {analyse_board.id} pour analyse '{analyse.reference}'")
        
        return analyse_board
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'analyse board: {str(e)}")
        db.session.rollback()
        raise e


def analyze_single_card_via_api(card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Utilise l'API interne pour analyser une carte spécifique.
    """
    try:
        card_name = card_data.get('name', 'N/A')
        
        logger.info(f"Début de l'analyse du ticket: {card_name}")
        logger.debug(f"Card ID: {card_id}")
        
        # Vérifier d'abord que le serveur est disponible
        if not check_flask_server_running():
            error_msg = 'Serveur Flask non disponible - analyse du ticket impossible'
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        
        # URL de l'API pour analyser une carte unique
        api_url = f"http://localhost:5000/api/trello/card/{card_id}/analyze"
        
        logger.debug(f"Appel API: {api_url}")
        
        # Appel à l'API
        response = requests.post(api_url, json=card_data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        logger.info(f"Analyse du ticket terminée avec succès")
        logger.debug(f"Résultat: {result}")
        
        return {
            'success': True,
            'analysis_result': result
        }
            
    except requests.exceptions.RequestException as e:
        error_msg = f'Erreur de requête API: {str(e)}'
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f'Erreur lors de l\'analyse: {str(e)}'
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


def save_ticket_to_database(analyse_board: AnalyseBoard, card_data: Dict[str, Any], analysis_result: Dict[str, Any], is_reanalysis: bool = False) -> Optional[Tickets]:
    """
    Sauvegarde le ticket analysé dans la table tickets.
    Pour les réanalyses, créer un nouveau ticket avec un identifiant unique.
    """
    try:
        logger.info("Sauvegarde du ticket dans la base de données...")
        
        # Extraire les données d'analyse
        criticality_level = analysis_result.get('criticality_level', 'low')
        analysis_details = analysis_result.get('analysis_details', {})
        
        # Créer les métadonnées du ticket
        ticket_metadata = {
            'name': card_data.get('name'),
            'desc': card_data.get('desc', ''),
            'due': card_data.get('due'),
            'url': card_data.get('url'),
            'list_name': card_data.get('list_name'),
            'board_name': card_data.get('board_name'),
            'labels': card_data.get('labels', []),
            'members': card_data.get('members', []),
            'analysis_result': analysis_result,
            'is_reanalysis': is_reanalysis
        }
        
        # Pour les réanalyses, créer un identifiant unique
        trello_ticket_id = card_data.get('id')
        if is_reanalysis:
            # Ajouter un suffixe unique basé sur le timestamp
            timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
            trello_ticket_id = f"{card_data.get('id')}_reanalyse_{timestamp_suffix}"
            logger.info(f"🔄 RÉANALYSE - Nouvel ID généré: {trello_ticket_id}")
        
        # Créer l'entrée ticket
        ticket = Tickets(
            analyse_board_id=analyse_board.id,
            trello_ticket_id=trello_ticket_id,
            ticket_metadata=ticket_metadata,
            criticality_level=criticality_level,
            createdAt=datetime.now()
        )
        
        # Sauvegarder en base
        db.session.add(ticket)
        db.session.commit()
        
        logger.info(f"Ticket sauvegardé avec succès: ID {ticket.id_ticket}")
        logger.info(f"Trello ID: {trello_ticket_id}")
        logger.info(f"Criticité: {criticality_level}")
        
        return ticket
        
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du ticket: {str(e)}")
        db.session.rollback()
        return None


def analyze_single_ticket(card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse un ticket Trello spécifique et l'enregistre dans la base.
    """
    try:
        card_name = card_data.get('name', 'Ticket sans nom')
        board_id = card_data.get('board_id', '')
        board_name = card_data.get('board_name', 'Board inconnu')
        
        logger.info(f"Début de l'analyse complète du ticket: {card_name}")
        logger.info(f"Board: {board_name}")
        logger.info(f"Card ID: {card_id}")
        
        # 0. Vérifier si le ticket a déjà été analysé
        existing_info = check_existing_ticket_analysis(card_id)
        
        # 1. Créer une session d'analyse dédiée
        analyse = create_ticket_analyse_session(card_name, board_name, card_id, existing_info)
        
        # 2. Créer l'analyse board
        analyse_board = create_analyse_board_for_ticket(analyse, board_id, board_name)
        
        # 3. Analyser le ticket via l'API
        analysis_api_result = analyze_single_card_via_api(card_id, card_data)
        
        if not analysis_api_result.get('success'):
            error_msg = analysis_api_result.get('error', 'Erreur lors de l\'analyse')
            logger.error(f"Échec de l'analyse: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'analyse_id': analyse.analyse_id,
                'reference': analyse.reference
            }
        
        # 4. Sauvegarder le ticket analysé
        analysis_result = analysis_api_result.get('analysis_result', {})
        is_reanalysis = existing_info.get('exists', False)
        ticket = save_ticket_to_database(analyse_board, card_data, analysis_result, is_reanalysis)
        
        if not ticket:
            error_msg = "Erreur lors de la sauvegarde du ticket"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'analyse_id': analyse.analyse_id,
                'reference': analyse.reference
            }
        
        # 5. Résultat final
        result = {
            'success': True,
            'message': 'Ticket analysé et sauvegardé avec succès',
            'analyse_id': analyse.analyse_id,
            'reference': analyse.reference,
            'analyse_board_id': analyse_board.id,
            'ticket_id': ticket.id_ticket,
            'card_id': card_id,
            'card_name': card_name,
            'board_name': board_name,
            'criticality_level': ticket.criticality_level,
            'analysis_result': analysis_result,
            'existing_ticket_info': existing_info,
            'is_reanalysis': existing_info.get('exists', False)
        }
        
        logger.info(f"Analyse complète terminée avec succès!")
        logger.info(f"Référence analyse: {analyse.reference}")
        logger.info(f"Ticket ID: {ticket.id_ticket}")
        logger.info(f"Criticité: {ticket.criticality_level}")
        
        return result
        
    except Exception as e:
        error_msg = f"Erreur lors de l'analyse complète: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


def print_analysis_summary(result: Dict[str, Any]) -> None:
    """
    Affiche un résumé de l'analyse effectuée.
    """
    logger.info("=" * 60)
    logger.info("RÉSUMÉ DE L'ANALYSE DU TICKET")
    logger.info("=" * 60)
    
    if result.get('success'):
        is_reanalysis = result.get('is_reanalysis', False)
        existing_info = result.get('existing_ticket_info', {})
        total_analyses = existing_info.get('total_analyses', 0)
        
        status_icon = f"🔄 RÉANALYSE #{total_analyses + 1}" if is_reanalysis else "✨ NOUVELLE ANALYSE #1"
        
        logger.info(f"{status_icon} RÉUSSIE")
        logger.info(f"Référence: {result.get('reference')}")
        logger.info(f"Nom du ticket: {result.get('card_name')}")
        logger.info(f"Board: {result.get('board_name')}")
        logger.info(f"Card ID Trello: {result.get('card_id', 'N/A')}")
        logger.info(f"Criticité: {result.get('criticality_level')}")
        logger.info(f"ID Analyse: {result.get('analyse_id')}")
        logger.info(f"ID Ticket: {result.get('ticket_id')}")
        
        # Afficher l'historique complet si c'est une réanalyse
        if is_reanalysis and total_analyses > 0:
            logger.info("🗂️ HISTORIQUE COMPLET DES ANALYSES:")
            all_tickets = existing_info.get('all_tickets', [])
            for i, ticket_info in enumerate(all_tickets, 1):
                logger.info(f"   {i}. Ticket ID: {ticket_info.get('id')} | "
                          f"Date: {ticket_info.get('date', 'N/A')[:16]} | "
                          f"Criticité: {ticket_info.get('criticality', 'N/A')}")
            logger.info(f"   {total_analyses + 1}. Ticket ID: {result.get('ticket_id')} | "
                      f"Date: NOUVELLE | "
                      f"Criticité: {result.get('criticality_level')}")
        
        analysis_details = result.get('analysis_result', {}).get('analysis_details', {})
        if analysis_details:
            logger.info("📊 DÉTAILS DE L'ANALYSE:")
            for key, value in analysis_details.items():
                logger.info(f"  {key}: {value}")
                
        # Message de traçabilité
        if is_reanalysis:
            previous_ticket_id = existing_info.get('previous_ticket_id', 'N/A')
            logger.info(f"🔗 TRAÇABILITÉ: Ce ticket fait référence au ticket original ID: {previous_ticket_id}")
            logger.info(f"🔍 Pour consulter l'historique complet, recherchez tous les tickets avec Card ID: {result.get('card_id', 'N/A')}")
    else:
        logger.error(f"❌ ÉCHEC DE L'ANALYSE")
        logger.error(f"Erreur: {result.get('error')}")
        if result.get('reference'):
            logger.info(f"Référence créée: {result.get('reference')}")


def main():
    """
    Fonction principale - EXEMPLE D'UTILISATION.
    Modifiez les données selon votre carte Trello.
    """
    logger.info("AGENT D'ANALYSE D'UN TICKET SPÉCIFIQUE")
    logger.info("=" * 50)
    
    # EXEMPLE DE DONNÉES DE CARTE - MODIFIEZ SELON VOS BESOINS
    card_id = "exemple_card_id_123"
    card_data = {
        "id": card_id,
        "name": "Corriger bug critique connexion utilisateur",
        "desc": "Bug critique empêchant la connexion des utilisateurs. Impact: tous les utilisateurs affectés. Priorité maximale.",
        "due": "2025-07-25T10:00:00Z",
        "list_name": "En cours",
        "board_id": "64a1b2c3d4e5f6789",
        "board_name": "Développement Application",
        "labels": [
            {"name": "urgent", "color": "red"},
            {"name": "bug", "color": "orange"}
        ],
        "members": [
            {"fullName": "John Doe", "username": "johndoe"}
        ],
        "url": "https://trello.com/c/abc123/corriger-bug-connexion"
    }
    
    logger.info(f"Analyse du ticket: {card_data['name']}")
    
    # Vérifier que le serveur Flask est en cours d'exécution
    logger.info("Vérification du serveur Flask...")
    if not check_flask_server_running():
        logger.error("Le serveur Flask n'est pas en cours d'exécution!")
        logger.error("Démarrez le serveur avec 'python run.py' avant d'exécuter ce script")
        sys.exit(1)

    # Créer l'application Flask
    app = create_app()
    
    with app.app_context():
        try:
            # Analyser le ticket
            result = analyze_single_ticket(card_id, card_data)
            
            # Afficher le résumé
            print_analysis_summary(result)
            
            if result.get('success'):
                logger.info("Analyse terminée avec succès!")
                logger.info(f"Vous pouvez consulter le ticket dans l'interface web avec l'analyse: {result.get('reference')}")
            else:
                logger.error("Analyse échouée!")
                sys.exit(1)
            
        except Exception as e:
            logger.error(f"Erreur fatale: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
