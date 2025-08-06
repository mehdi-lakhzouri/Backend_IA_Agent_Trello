from flask import Blueprint, jsonify, request
import logging
logger = logging.getLogger('agent_analyse')
import os
from datetime import datetime
from app.services.trello_service import get_trello_user_info
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.models.trello_models import TrelloCard, CriticalityAnalysis, BoardAnalysisSummary, Config, Analyse, AnalyseBoard, Tickets, TicketAnalysisHistory
from app import db
from app.utils.crypto_service import crypto_service
from app.services.database_service import DatabaseService
from sqlalchemy import func
import requests
from tools.add_comment_tool import add_comment_to_card
import traceback
from tools.move_card_tool import move_card_to_list
import html
import re
from tools.add_etiquette_tool import apply_criticality_label_with_creation
from tools.add_etiquette_tool import apply_criticality_label_with_creation
trello_bp = Blueprint('trello', __name__)

# Note: Les routes de connexion Trello sont maintenant gérées côté frontend

@trello_bp.route('/api/trello/board/<board_id>/list/<list_id>/analyze', methods=['POST'])
def analyze_list_cards(board_id, list_id):
    """
    Analyse toutes les cartes d'une liste spécifique dans un board Trello.
    
    Body JSON attendu:
    {
        "token": "string",
        "board_name": "string",
        "list_name": "string",
        "analyse_board_id": "integer" (optionnel - pour lier à une session d'analyse existante)
    }
    
    Response:
    {
        "status": "success",
        "board_analysis": {
            "board_id": "string",
            "board_name": "string", 
            "list_id": "string",
            "list_name": "string",
            "total_cards": integer,
            "criticality_distribution": {...},
            "success_rate": float,
            "analyzed_at": "datetime"
        },
        "cards_analysis": [...],
        "saved_tickets": [...] (si analyse_board_id fourni)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Corps de requête JSON requis"}), 400
        
        token = data.get('token')
        board_name = data.get('board_name', 'Board sans nom')
        list_name = data.get('list_name', 'Liste sans nom')
        analyse_board_id = data.get('analyse_board_id')
        
        if not token:
            return jsonify({"error": "Token Trello requis"}), 400
        
        # Récupérer les cartes de la liste via l'API Trello
        try:
            cards_url = f"https://api.trello.com/1/lists/{list_id}/cards"
            params = {
                'key': os.environ.get('TRELLO_API_KEY'),
                'token': token,
                'fields': 'id,name,desc,due,url,dateLastActivity',
                'attachments': 'false',
                'members': 'true',
                'labels': 'true'
            }
            
            print(f"[DEBUG] Récupération des cartes de la liste {list_id}")
            print(f"[DEBUG] URL: {cards_url}")
            print(f"[DEBUG] Clé API présente: {'✓' if os.environ.get('TRELLO_API_KEY') else '✗'}")
            
            response = requests.get(cards_url, params=params)
            response.raise_for_status()
            cards_data = response.json()
            
            print(f"[DEBUG] Nombre de cartes trouvées: {len(cards_data)}")
            if cards_data:
                print(f"[DEBUG] Première carte: {cards_data[0].get('name', 'Sans nom')}")
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Erreur API Trello: {str(e)}")
            return jsonify({"error": f"Erreur lors de la récupération des cartes: {str(e)}"}), 500
        
        if not cards_data:
            return jsonify({
                "status": "success",
                "message": "Aucune carte trouvée dans cette liste",
                "board_analysis": {
                    "board_id": board_id,
                    "board_name": board_name,
                    "list_id": list_id,
                    "list_name": list_name,
                    "total_cards": 0,
                    "analyzed_at": datetime.now().isoformat()
                },
                "cards_analysis": []
            }), 200
        
        # Initialiser l'analyseur de criticité
        analyzer = CriticalityAnalyzer()
        
        # Analyser chaque carte
        analysis_results = []
        saved_tickets = []
        

        

        for card in cards_data:
            existing_ticket = Tickets.get_by_ticket_id(card['id'])
            if existing_ticket and existing_ticket.ticket_metadata:
                # Recherche d'une analyse précédente dans l'historique
                last_analysis = TicketAnalysisHistory.query.filter_by(ticket_id=existing_ticket.id_ticket).order_by(TicketAnalysisHistory.analyzed_at.desc()).first()
                if last_analysis:
                    print(f"📌 Ticket {card['id']} déjà analysé, utilisation du résultat en cache")
                    result = {
                        'success': True,
                        'criticality_level': last_analysis.criticality_level,
                        'justification': last_analysis.analyse_justification.get('justification') if last_analysis.analyse_justification else None,
                        'analyzed_at': last_analysis.analyzed_at.isoformat() if last_analysis.analyzed_at else None
                    }
                    analysis_results.append(result)
                    if analyse_board_id:
                        saved_tickets.append({
                            'ticket_id': card['id'],
                            'card_name': card['name'],
                            'from_cache': True
                        })
                    continue
            
            # Préparer les données de la carte pour l'analyse (nouveau ticket)
            card_data = {
                'id': card['id'],
                'name': card['name'],
                'desc': card.get('desc', ''),
                'due': card.get('due'),
                'list_name': list_name,
                'board_id': board_id,
                'board_name': board_name,
                'labels': card.get('labels', []),
                'members': card.get('members', []),
                'url': card['url']
            }

            # Analyser la criticité (nouveau ticket seulement)
            print(f"🔍 Analyse en cours pour le nouveau ticket {card['id']}...")
            result = analyzer.analyze_card_criticality(card_data)
            result['analyzed_at'] = datetime.now().isoformat()
            analysis_results.append(result)
            print(f"[DEBUG] Résultat analyse pour {card['id']}: success={result.get('success', False)}, criticality={result.get('criticality_level', 'N/A')}")



            # Ajouter l'étiquette de criticité sur la carte Trello après analyse
            try:
                if result.get('success', False) and result.get('criticality_level'):
                    logger.info(f"Ajout de l'étiquette '{result['criticality_level']}' sur la carte {card['id']} ({card['name']})")
                    apply_criticality_label_with_creation(
                        card_id=card['id'],
                        board_id=board_id,
                        token=token,
                        criticality_level=result['criticality_level']
                    )
                    logger.info(f"Étiquette '{result['criticality_level']}' ajoutée avec succès sur la carte {card['id']}")
            except Exception as label_error:
                logger.error(f"Erreur lors de l'ajout de l'étiquette sur la carte {card['id']} : {str(label_error)}")

            # Ajouter la justification comme commentaire sur la carte Trello
            try:
                justification = result.get('justification')
                if result.get('success', False) and justification:
                    logger.info(f"Ajout du commentaire (justification) sur la carte {card['id']} ({card['name']})")
                    add_comment_to_card(
                        card_id=card['id'],
                        token=token,
                        comment=justification
                    )
                    logger.info(f"Commentaire ajouté avec succès sur la carte {card['id']}")
            except Exception as comment_error:
                logger.error(f"Erreur lors de l'ajout du commentaire sur la carte {card['id']} : {str(comment_error)}")

            # Déplacer la carte vers la liste cible si configurée
            try:
                if result.get('success', False):
                    # Récupérer la configuration avec targetListId
                    config = Config.get_latest_config()
                    if config and config.config_data:
                        target_list_id = config.config_data.get('targetListId')
                        target_list_name = config.config_data.get('targetListName', 'Liste cible')
                        
                        if target_list_id:
                            logger.info(f"Déplacement de la carte {card['id']} vers la liste '{target_list_name}' ({target_list_id})")
                            move_result = move_card_to_list(
                                card_id=card['id'],
                                new_list_id=target_list_id,
                                token=token
                            )
                            logger.info(f"Carte {card['id']} déplacée avec succès vers la liste '{target_list_name}'")
                            
                            # Ajouter l'info du déplacement au résultat
                            result['card_moved'] = True
                            result['target_list_id'] = target_list_id
                            result['target_list_name'] = target_list_name
                        else:
                            logger.warning(f"Aucune liste cible (targetListId) configurée pour le déplacement")
                            result['card_moved'] = False
                            result['move_error'] = "Aucune liste cible configurée"
            except Exception as move_error:
                logger.error(f"Erreur lors du déplacement de la carte {card['id']} : {str(move_error)}")
                result['card_moved'] = False
                result['move_error'] = str(move_error)

            # Si analyse_board_id est fourni, sauvegarder dans la table tickets et dans l'historique
            print(f"[DEBUG] Vérification sauvegarde - analyse_board_id: {analyse_board_id}, success: {result.get('success', False)}")
            if analyse_board_id and result.get('success', False):
                print(f"[DEBUG] Sauvegarde du ticket {card['id']} en cours...")
                try:
                    analyse_board = AnalyseBoard.query.get(analyse_board_id)
                    analyse_id = analyse_board.analyse_id if analyse_board else None
                    # Vérifier si le ticket existe déjà
                    if not Tickets.exists_by_ticket_id(card['id']):
                        ticket = Tickets(
                            analyse_board_id=analyse_board_id,
                            ticket_id=card['id'],
                            board_name=board_name,  # Ajouter le nom du board pour la traçabilité
                            ticket_metadata={
                                'name': card['name'],
                                'desc': card.get('desc', ''),
                                'due': card.get('due'),
                                'url': card['url'],
                                'labels': card.get('labels', []),
                                'members': card.get('members', []),
                                'board_id': board_id,
                                'board_name': board_name,
                                'list_id': list_id,
                                'list_name': list_name
                            }
                        )
                        db.session.add(ticket)
                        db.session.flush()  # Pour obtenir ticket.id_ticket
                    else:
                        ticket = Tickets.get_by_ticket_id(card['id'])
                    # Enregistrer l'analyse dans l'historique
                    history = TicketAnalysisHistory(
                        ticket_id=ticket.id_ticket,
                        analyse_id=analyse_id,
                        analyse_justification={'justification': result.get('justification')},
                        criticality_level=result.get('criticality_level'),
                        analyzed_at=datetime.now()
                        # Note: reanalyse a été déplacé vers la table analyse
                    )
                    db.session.add(history)
                    saved_tickets.append({
                        'ticket_id': card['id'],
                        'card_name': card['name']
                    })
                    print(f"[DEBUG] Ticket {card['id']} ajouté à la liste de sauvegarde")
                except Exception as ticket_error:
                    print(f"Erreur lors de la sauvegarde du ticket {card['id']}: {str(ticket_error)}")
            else:
                print(f"[DEBUG] Ticket {card['id']} ignoré - analyse_board_id: {analyse_board_id}, success: {result.get('success', False)}")
        
        # Commit des tickets sauvegardés
        if saved_tickets:
            try:
                db.session.commit()
            except Exception as commit_error:
                db.session.rollback()
                print(f"Erreur lors du commit des tickets: {str(commit_error)}")
                saved_tickets = []
        
        # Calculer les statistiques
        total_cards = len(analysis_results)
        successful_analyses = [r for r in analysis_results if r.get('success', False)]
        
        criticality_counts = {
            'CRITICAL_TOTAL': len(successful_analyses),  # Tous les tickets analysés sont critiques
            'NON_CRITICAL': 0,  # Plus de tickets non-critiques
            'HIGH': len([r for r in successful_analyses if r.get('criticality_level') == 'HIGH']),
            'MEDIUM': len([r for r in successful_analyses if r.get('criticality_level') == 'MEDIUM']),
            'LOW': len([r for r in successful_analyses if r.get('criticality_level') == 'LOW'])
        }
        
        success_rate = len(successful_analyses) / total_cards if total_cards > 0 else 0
        
        response = {
            "status": "success",
            "board_analysis": {
                "board_id": board_id,
                "board_name": board_name,
                "list_id": list_id,
                "list_name": list_name,
                "total_cards": total_cards,
                "criticality_distribution": criticality_counts,
                "success_rate": round(success_rate * 100, 2),
                "analyzed_at": datetime.now().isoformat()
            },
            "cards_analysis": analysis_results
        }
        
        # Ajouter les tickets sauvegardés à la réponse si applicable
        if saved_tickets:
            response["saved_tickets"] = saved_tickets
            response["tickets_saved_count"] = len(saved_tickets)
        
        return jsonify(response), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de l'analyse: {str(e)}"}), 500


@trello_bp.route('/api/trello/card/<card_id>/add-label', methods=['POST'])
def add_label_to_card(card_id):
    """
    Add a criticality label to a specific Trello card.
    
    Body JSON attendu:
    {
        "board_id": "string",
        "token": "string",
        "criticality_level": "HIGH|MEDIUM|LOW"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Corps de requête JSON requis"}), 400
        
        board_id = data.get('board_id')
        token = data.get('token')
        criticality_level = data.get('criticality_level')
        
        # Validation des champs requis
        required_fields = ['board_id', 'token', 'criticality_level']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Champ {field} requis"}), 400
        
        # Validation du niveau de criticité
        if criticality_level.upper() not in ['HIGH', 'MEDIUM', 'LOW']:
            return jsonify({"error": "criticality_level doit être HIGH, MEDIUM ou LOW"}), 400
        
        
        
        # Appliquer le label sur la carte
        try:
            result = apply_criticality_label_with_creation(
                card_id=card_id,
                board_id=board_id,
                token=token,
                criticality_level=criticality_level.upper()
            )
            
            return jsonify({
                "status": "success",
                "message": f"Label de criticité '{criticality_level.upper()}' ajouté à la carte {card_id}",
                "card_id": card_id,
                "criticality_level": criticality_level.upper(),
                "trello_response": result
            }), 200
            
        except Exception as label_error:
            return jsonify({
                "status": "error",
                "message": f"Erreur lors de l'ajout du label: {str(label_error)}"
            }), 500
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors du traitement: {str(e)}"}), 500


@trello_bp.route('/api/trello/card/<card_id>/add-comment', methods=['POST'])
def add_comment_to_card_endpoint(card_id):
    """
    Add a comment to a specific Trello card.
    
    Body JSON attendu:
    {
        "token": "string",
        "comment": "string"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Corps de requête JSON requis"}), 400
        
        token = data.get('token')
        comment = data.get('comment')
        
        # Validation des champs requis
        required_fields = ['token', 'comment']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Champ {field} requis"}), 400
        
        
        
        # Ajouter le commentaire à la carte
        try:
            result = add_comment_to_card(
                card_id=card_id,
                token=token,
                comment=comment
            )
            
            return jsonify({
                "status": "success",
                "message": f"Commentaire ajouté à la carte {card_id}",
                "card_id": card_id,
                "comment": comment,
                "trello_response": result
            }), 200
            
        except Exception as comment_error:
            return jsonify({
                "status": "error",
                "message": f"Erreur lors de l'ajout du commentaire: {str(comment_error)}"
            }), 500
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors du traitement: {str(e)}"}), 500





@trello_bp.route('/api/trello/card/<card_id>/analyze', methods=['POST'])
def analyze_single_card_criticality(card_id):
    """
    Analyse la criticité d'une seule card Trello.
    
    Body JSON attendu:
    {
        "name": "string",
        "desc": "string",
        "due": "string|null",
        "list_name": "string",
        "board_id": "string",
        "board_name": "string",
        "labels": [...],
        "members": [...],
        "url": "string"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Corps de requête JSON requis"}), 400
        
        # Ajouter l'ID de la card aux données
        data['id'] = card_id
        
        # Valider les champs requis
        required_fields = ['name', 'board_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Champ {field} requis"}), 400
        
        # Initialiser l'analyseur de criticité
        analyzer = CriticalityAnalyzer()
        
        # Analyser la card
        result = analyzer.analyze_card_criticality(data)
        result['analyzed_at'] = datetime.now().isoformat()
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'analyse: {str(e)}"}), 500



@trello_bp.route('/api/trello/config-board-subscription', methods=['POST'])
def config_board_subscription():
    """
    Capture les données Trello et les enregistre en base.
    Attend: token, board_id, board_name, list_id, list_name
    """
    try:
        data = request.get_json()
        print(f"[DEBUG] Données reçues sur /api/trello/config-board-subscription: {data}")
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Corps de requête JSON requis"
            }), 400
        
        # Extraction des champs (accepte camelCase et snake_case)
        token = data.get('token')
        board_id = data.get('board_id') or data.get('boardId')
        board_name = data.get('board_name') or data.get('boardName')
        list_id = data.get('list_id') or data.get('listId')
        list_name = data.get('list_name') or data.get('listName')
        
        # Vérification des champs obligatoires
        required_fields = [
            ('token', token),
            ('board_id', board_id),
            ('board_name', board_name),
            ('list_id', list_id),
            ('list_name', list_name)
        ]
        missing_fields = [name for name, value in required_fields if not value]
        
        if missing_fields:
            return jsonify({
                "status": "error",
                "message": f"Champs manquants : {', '.join(missing_fields)}"
            }), 400
        
        # Création automatique de la base et des tables
        db_service = DatabaseService()
        if not db_service.ensure_database_and_tables():
            return jsonify({
                "status": "error",
                "message": "Erreur lors de la création de la base de données"
            }), 500

        # Enregistrement en base avec toutes les données dans config_data
        config = Config(config_data=data)
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Configuration Trello enregistrée avec succès",
            "data": data,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la configuration: {str(e)}"
        }), 500


@trello_bp.route('/api/trello/config-board-subscription', methods=['PUT'])
def update_board_subscription():
    """
    Met à jour une configuration d'abonnement aux boards Trello existante.
    Attend: id, et les champs à mettre à jour (ex: targetListId, targetListName)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Corps de requête JSON requis"
            }), 400
        
        config_id = data.get('id')
        if not config_id:
            return jsonify({
                "status": "error",
                "message": "ID de configuration requis"
            }), 400
        
        # Récupérer la configuration existante
        config = Config.query.get(config_id)
        if not config:
            return jsonify({
                "status": "error",
                "message": f"Configuration avec l'ID {config_id} introuvable"
            }), 404
        
        # Mettre à jour les données de configuration
        updated_config_data = config.config_data.copy()
        
        # Champs autorisés à la mise à jour
        allowed_fields = ['targetListId', 'targetListName', 'token', 'boardName', 'listName']
        for field in allowed_fields:
            if field in data:
                updated_config_data[field] = data[field]
        
        config.config_data = updated_config_data
        config.updatedAt = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Configuration mise à jour avec succès",
            "data": updated_config_data,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la mise à jour: {str(e)}"
        }), 500


@trello_bp.route('/api/trello/config-board-subscription', methods=['GET'])
def get_board_subscriptions():
    """
    Récupère toutes les configurations d'abonnement aux boards Trello.
    """
    try:
        configs = Config.query.all()
        
        config_list = []
        for config in configs:
            config_list.append({
                "id": config.id,
                "board_id": config.config_data.get('boardId'),
                "board_name": config.config_data.get('boardName'),
                "created_at": config.createdAt.isoformat() if config.createdAt else None
            })
        
        return jsonify({
            "status": "success",
            "total": len(config_list),
            "configurations": config_list
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la récupération: {str(e)}"
        }), 500




@trello_bp.route('/api/trello/config-board-subscription/<board_id>/token', methods=['GET'])
def get_decrypted_token(board_id):
    """
    Récupère le token décrypté pour un board spécifique.
    ATTENTION: Route sensible - à protéger en production.
    """
    try:
        config = Config.query.filter_by(board_id=board_id).first()
        
        if not config:
            return jsonify({
                "status": "error",
                "message": f"Configuration non trouvée pour le board {board_id}"
            }), 404
        
        # Décrypter le token
        try:
            decrypted_token = crypto_service.decrypt_token(config.trello_token)
        except Exception as crypto_error:
            return jsonify({
                "status": "error",
                "message": f"Erreur lors du décryptage: {str(crypto_error)}"
            }), 500
        
        return jsonify({
            "status": "success",
            "board_id": board_id,
            "board_name": config.board_name,
            "trello_token": decrypted_token
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la récupération: {str(e)}"
        }), 500


@trello_bp.route('/api/analyses', methods=['GET'])
def get_analyses():
    """
    API avec pagination, filtres et tri pour les analyses.

    Paramètres :
    - page (int) : Page actuelle (défaut: 1)
    - perPage (int) : Éléments par page (5|10|15, défaut: 10)
    - filters[] (list) : Filtres sous forme ["champ:opérateur:valeur"]
      Ex: ["createdAt:gte:2023-01-01", "tickets_count:gt:5"]
    - orderBy (str) : Champ de tri (createdAt, tickets_count, défaut: createdAt)
    - orderDirection (str) : asc ou desc (défaut: desc)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('perPage', 5, type=int)
        filters = request.args.getlist('filters[]')
        order_by = request.args.get('orderBy', 'createdAt', type=str)
        order_direction = request.args.get('orderDirection', 'desc', type=str)

        per_page = per_page if per_page in {5, 10, 15} else 10
        order_by = order_by if order_by in {'createdAt', 'tickets_count'} else 'createdAt'
        order_direction = order_direction if order_direction in {'asc', 'desc'} else 'desc'

        # Base query - utiliser ticket_analysis_history pour compter les tickets par analyse
        query = db.session.query(
            Analyse,
            func.count(TicketAnalysisHistory.id).label('tickets_count')
        ).select_from(Analyse) \
         .outerjoin(TicketAnalysisHistory, TicketAnalysisHistory.analyse_id == Analyse.analyse_id) \
         .group_by(Analyse.analyse_id)

        applied_filters = []

        for f in filters:
            try:
                field, operator, value = f.split(':')

                if field == 'createdAt':
                    value = datetime.strptime(value, '%Y-%m-%d').date()

                    if operator == 'gte':
                        query = query.filter(Analyse.createdAt >= value)
                    elif operator == 'lte':
                        query = query.filter(Analyse.createdAt <= value)
                    elif operator == 'eq':
                        query = query.filter(func.date(Analyse.createdAt) == value)
                    elif operator == 'gt':
                        query = query.filter(Analyse.createdAt > value)
                    elif operator == 'lt':
                        query = query.filter(Analyse.createdAt < value)
                    else:
                        continue

                    applied_filters.append({"field": field, "operator": operator, "value": str(value)})

                elif field == 'tickets_count':
                    value = int(value)

                    if operator == 'gt':
                        query = query.having(func.count(TicketAnalysisHistory.id) > value)
                    elif operator == 'gte':
                        query = query.having(func.count(TicketAnalysisHistory.id) >= value)
                    elif operator == 'lt':
                        query = query.having(func.count(TicketAnalysisHistory.id) < value)
                    elif operator == 'lte':
                        query = query.having(func.count(TicketAnalysisHistory.id) <= value)
                    elif operator == 'eq':
                        query = query.having(func.count(TicketAnalysisHistory.id) == value)
                    else:
                        continue

                    applied_filters.append({"field": field, "operator": operator, "value": value})

            except Exception as filter_error:
                continue  # Ignore malformed filter

        # Sorting
        if order_by == 'tickets_count':
            sort_column = func.count(Tickets.id_ticket)
        else:
            sort_column = getattr(Analyse, order_by)

        query = query.order_by(
            sort_column.desc() if order_direction == 'desc' else sort_column.asc()
        )

        # Pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # Format results
        analyses_data = []
        for analysis, tickets_count in pagination.items:
            analysis_dict = {
                "analyse_id": analysis.analyse_id,
                "reference": analysis.reference,
                "createdAt": analysis.createdAt.isoformat() if analysis.createdAt else None,
                "updatedAt": analysis.updatedAt.isoformat() if analysis.updatedAt else None,
                "tickets_count": tickets_count
            }
            analyses_data.append(analysis_dict)

        return jsonify({
            "status": "success",
            "data": analyses_data,
            "meta": {
                "pagination": {
                    "currentPage": pagination.page,
                    "perPage": pagination.per_page,
                    "totalPages": pagination.pages,
                    "totalItems": pagination.total,
                    "hasNext": pagination.has_next,
                    "hasPrev": pagination.has_prev
                },
                "filters": applied_filters,
                "sort": {
                    "orderBy": order_by,
                    "orderDirection": order_direction
                }
            }
        }), 200

    except Exception as e:
        print("❌ Une erreur est survenue dans /api/analyses :")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Erreur serveur: {str(e)}"
        }), 500



@trello_bp.route('/api/tickets', methods=['GET'])
def get_tickets():
    """
    Liste paginée des tickets d'une analyse spécifique, avec filtres et tri.
    """
    try:
        analyse_id = request.args.get('analyse_id', type=int)
        if not analyse_id:
            return jsonify({"status": "error", "message": "Paramètre analyse_id requis"}), 400

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('perPage', 10, type=int)
        filters = request.args.getlist('filters[]')
        order_by = request.args.get('orderBy', 'analyzed_at', type=str)
        order_direction = request.args.get('orderDirection', 'desc', type=str)

        per_page = per_page if per_page in {5, 10, 15} else 10
        order_by = order_by if order_by in {'criticality_level', 'analyzed_at', 'name'} else 'analyzed_at'
        order_direction = order_direction if order_direction in {'asc', 'desc'} else 'desc'

        # Import local nécessaire pour cette fonction
        from app.models.trello_models import TicketAnalysisHistory

        # Nouvelle logique : utiliser ticket_analysis_history pour trouver les tickets d'une analyse
        # sans duplication dans la table tickets
        query = db.session.query(Tickets).join(
            TicketAnalysisHistory, Tickets.id_ticket == TicketAnalysisHistory.ticket_id
        ).filter(TicketAnalysisHistory.analyse_id == analyse_id)

        applied_filters = []
        for f in filters:
            try:
                field, operator, value = f.split(':')
                if field == 'criticality_level' and operator == 'eq':
                    query = query.filter(Tickets.criticality_level == value.lower())
                    applied_filters.append({"field": field, "operator": operator, "value": value})
                elif field == 'name' and operator == 'contains':
                    query = query.filter(
                        func.json_unquote(func.json_extract(Tickets.ticket_metadata, '$.name')).ilike(f'%{value}%')
                    )
                    applied_filters.append({"field": field, "operator": operator, "value": value})
            except Exception:
                continue

        # Tri dynamique
        if order_by == 'criticality_level':
            sort_column = Tickets.criticality_level
        elif order_by == 'name':
            sort_column = func.json_unquote(func.json_extract(Tickets.ticket_metadata, '$.name'))
        elif order_by == 'analyzed_at':
            sort_column = func.json_unquote(func.json_extract(Tickets.ticket_metadata, '$.analysis_result.analyzed_at'))
        else:
            sort_column = Tickets.id_ticket

        query = query.order_by(sort_column.desc() if order_direction == 'desc' else sort_column.asc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        tickets_data = []
        for ticket in pagination.items:
            meta = ticket.ticket_metadata or {}
            # Récupérer la dernière analyse pour ce ticket avec info de réanalyse
            last_analysis = db.session.query(TicketAnalysisHistory).join(
                AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
            ).join(
                Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
            ).filter(
                TicketAnalysisHistory.ticket_id == ticket.id_ticket
            ).order_by(TicketAnalysisHistory.analyzed_at.desc()).first()
            
            if last_analysis:
                # Récupérer l'analyse associée pour le flag reanalyse
                analyse = db.session.query(Analyse).join(
                    AnalyseBoard, Analyse.analyse_id == AnalyseBoard.analyse_id
                ).filter(
                    AnalyseBoard.analyse_id == last_analysis.analyse_id
                ).first()
                
                justification = last_analysis.analyse_justification.get('justification') if last_analysis.analyse_justification else ''
                analyzed_at = last_analysis.analyzed_at.isoformat() if last_analysis.analyzed_at else None
                criticality_level = last_analysis.criticality_level.upper() if last_analysis.criticality_level else None
                is_reanalyse = analyse.reanalyse if analyse else False
            else:
                justification = ''
                analyzed_at = None
                criticality_level = None
                is_reanalyse = False

            tickets_data.append({
                "ticket_id": ticket.ticket_id,
                "id_ticket": ticket.id_ticket,
                "name": meta.get('name'),
                "desc": meta.get('desc'),
                "due": meta.get('due'),
                "url": meta.get('url'),
                "board_name": ticket.board_name,  # Ajouter le nom du board
                "criticality_level": criticality_level,
                "justification": justification,
                "analyzed_at": analyzed_at,
                "is_reanalyse": is_reanalyse  # Utiliser la variable calculée
            })

        return jsonify({
            "status": "success",
            "data": tickets_data,
            "meta": {
                "pagination": {
                    "currentPage": pagination.page,
                    "perPage": pagination.per_page,
                    "totalPages": pagination.pages,
                    "totalItems": pagination.total,
                    "hasNext": pagination.has_next,
                    "hasPrev": pagination.has_prev
                },
                "filters": applied_filters,
                "sort": {
                    "orderBy": order_by,
                    "orderDirection": order_direction
                }
            }
        }), 200

    except Exception as e:
        print("❌ Une erreur est survenue dans /api/tickets :")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Erreur serveur: {str(e)}"
        }), 500


@trello_bp.route('/api/analysis/cache/clear', methods=['POST'])
def clear_analysis_cache():
    """
    Supprime le cache d'analyse pour forcer une réanalyse de tous les tickets.
    
    Body JSON attendu (optionnel):
    {
        "ticket_id": "string" (optionnel - pour supprimer le cache d'un ticket spécifique)
    }
    """
    try:
        data = request.get_json() or {}
        ticket_id = data.get('ticket_id')
        
        if ticket_id:
            # Supprimer le cache pour un ticket spécifique
            success = Tickets.invalidate_analysis_cache(ticket_id)
            if success:
                return jsonify({
                    "status": "success",
                    "message": f"Cache d'analyse supprimé pour le ticket {ticket_id}",
                    "cleared_tickets": 1
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Ticket {ticket_id} introuvable ou sans cache"
                }), 404
        else:
            # Supprimer le cache pour tous les tickets
            cleared_count = Tickets.clear_all_analysis_cache()
            return jsonify({
                "status": "success",
                "message": f"Cache d'analyse supprimé pour {cleared_count} tickets",
                "cleared_tickets": cleared_count
            }), 200
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la suppression du cache: {str(e)}"
        }), 500


@trello_bp.route('/api/analysis/cache/status', methods=['GET'])
def get_cache_status():
    """
    Récupère les statistiques du cache d'analyse.
    """
    try:
        total_tickets = Tickets.query.count()
        
        # Compter les tickets avec cache d'analyse
        cached_tickets = 0
        uncached_tickets = 0
        
        tickets = Tickets.query.all()
        for ticket in tickets:
            if ticket.ticket_metadata and ticket.ticket_metadata.get('analysis_result'):
                cached_tickets += 1
            else:
                uncached_tickets += 1
        
        cache_ratio = (cached_tickets / total_tickets * 100) if total_tickets > 0 else 0
        
        return jsonify({
            "status": "success",
            "cache_stats": {
                "total_tickets": total_tickets,
                "cached_tickets": cached_tickets,
                "uncached_tickets": uncached_tickets,
                "cache_ratio_percent": round(cache_ratio, 2)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la récupération des statistiques: {str(e)}"
        }), 500


@trello_bp.route('/api/tickets/<ticket_id>/analysis', methods=['GET'])
def get_ticket_analysis(ticket_id):
    """
    Récupère le résultat d'analyse en cache pour un ticket spécifique.
    """
    try:
        cached_result = Tickets.get_cached_analysis(ticket_id)
        
        if cached_result:
            return jsonify({
                "status": "success",
                "ticket_id": ticket_id,
                "analysis_result": cached_result,
                "from_cache": True
            }), 200
        else:
            return jsonify({
                "status": "not_found",
                "message": f"Aucune analyse en cache pour le ticket {ticket_id}"
            }), 404
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la récupération de l'analyse: {str(e)}"
        }), 500

@trello_bp.route('/api/trello/card/<card_id>/move', methods=['PUT'])
def move_card(card_id):
    """
    Déplace une carte Trello vers une autre liste.
    
    Body JSON attendu :
    {
        "token": "string",
        "new_list_id": "string"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Corps de requête JSON requis"}), 400
        token = data.get('token')
        new_list_id = data.get('new_list_id')
        if not token or not new_list_id:
            return jsonify({"error": "token et new_list_id sont requis"}), 400
        result = move_card_to_list(card_id, new_list_id, token)
        return jsonify({"status": "success", "result": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    


@trello_bp.route('/api/tickets/<ticket_id>/reanalyze', methods=['POST'])
def reanalyze_ticket(ticket_id):
    """
    Réanalyse un ticket précis, enregistre le résultat dans ticket_analysis_history et retourne le nouveau résultat.
    """
    try:
        from app.services.criticality_analyzer import CriticalityAnalyzer
        ticket = Tickets.get_by_ticket_id(ticket_id)
        if not ticket:
            return jsonify({"status": "error", "message": f"Ticket {ticket_id} introuvable"}), 404

        meta = ticket.ticket_metadata or {}
        # Préparer les données pour l'analyse
        card_data = {
            'id': ticket.ticket_id,
            'name': meta.get('name'),
            'desc': meta.get('desc', ''),
            'due': meta.get('due'),
            'list_name': meta.get('list_name'),
            'board_id': meta.get('board_id'),
            'board_name': meta.get('board_name'),
            'labels': meta.get('labels', []),
            'members': meta.get('members', []),
            'url': meta.get('url')
        }
        analyzer = CriticalityAnalyzer()
        result = analyzer.analyze_card_criticality(card_data)
        result['analyzed_at'] = datetime.now().isoformat()

        # Créer une nouvelle session d'analyse pour la réanalyse
        reanalyse_session = Analyse(
            reference=f"REANALYSE-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            reanalyse=True,  # Marquer comme réanalyse
            createdAt=datetime.now()
        )
        db.session.add(reanalyse_session)
        db.session.flush()  # Pour obtenir l'ID

        # Créer un nouveau AnalyseBoard pour cette réanalyse
        analyse_board = AnalyseBoard(
            analyse_id=reanalyse_session.analyse_id,
            platform='trello',
            createdAt=datetime.now()
        )
        db.session.add(analyse_board)
        db.session.flush()  # Pour obtenir l'ID

        # Enregistrer dans l'historique (sans dupliquer le ticket dans la table tickets)
        history = TicketAnalysisHistory(
            ticket_id=ticket.id_ticket,
            analyse_id=reanalyse_session.analyse_id,  # Utiliser la nouvelle session de réanalyse
            analyse_justification={'justification': result.get('justification')},
            criticality_level=result.get('criticality_level'),
            analyzed_at=datetime.now()
            # Note: reanalyse a été déplacé vers la table analyse
        )
        db.session.add(history)
        
        # Mettre à jour le cache d'analyse dans ticket_metadata
        if ticket.ticket_metadata:
            ticket.ticket_metadata['analysis_result'] = result
        else:
            ticket.ticket_metadata = {'analysis_result': result}
        db.session.add(ticket)
        
        db.session.commit()

        return jsonify({
            "status": "success",
            "ticket_id": ticket_id,
            "analysis_result": result
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Erreur lors de la réanalyse: {str(e)}"}), 500


@trello_bp.route('/api/tickets/<ticket_id>/analysis/history', methods=['GET'])
def get_ticket_analysis_history(ticket_id):
    """
    Retourne l'historique complet des analyses pour un ticket.
    """
    try:
        ticket = Tickets.get_by_ticket_id(ticket_id)
        if not ticket:
            return jsonify({"status": "error", "message": f"Ticket {ticket_id} introuvable"}), 404

        # Récupérer l'historique avec l'information de réanalyse
        history_entries = db.session.query(TicketAnalysisHistory, Analyse).join(
            AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
        ).join(
            Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
        ).filter(
            TicketAnalysisHistory.ticket_id == ticket.id_ticket
        ).order_by(TicketAnalysisHistory.analyzed_at.desc()).all()

        history_list = []
        for entry, analyse in history_entries:
            history_list.append({
                "analysis_id": entry.id,
                "analyse_id": entry.analyse_id,
                "justification": entry.analyse_justification.get('justification') if entry.analyse_justification else '',
                "criticality_level": entry.criticality_level,
                "analyzed_at": entry.analyzed_at.isoformat() if entry.analyzed_at else None,
                "reanalyse": analyse.reanalyse  # Utiliser le champ reanalyse de la table analyse
            })

        return jsonify({
            "status": "success",
            "ticket_id": ticket_id,
            "board_name": ticket.board_name,
            "history": history_list,
            "total": len(history_list)
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de la récupération de l'historique: {str(e)}"}), 500


@trello_bp.route('/api/analysis/statistics', methods=['GET'])
def get_analysis_statistics():
    """
    Retourne des statistiques sur les analyses et réanalyses.
    """
    try:
        # Statistiques générales
        total_analyses = TicketAnalysisHistory.query.count()
        total_tickets = Tickets.query.count()
        
        # Compter les réanalyses en utilisant la table analyse
        total_reanalyses = db.session.query(TicketAnalysisHistory).join(
            AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
        ).join(
            Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
        ).filter(
            Analyse.reanalyse == True
        ).count()
        
        total_initial_analyses = total_analyses - total_reanalyses
        
        # Répartition par niveau de criticité
        criticality_stats = {
            'high': TicketAnalysisHistory.query.filter_by(criticality_level='high').count(),
            'medium': TicketAnalysisHistory.query.filter_by(criticality_level='medium').count(),
            'low': TicketAnalysisHistory.query.filter_by(criticality_level='low').count()
        }
        
        # Statistiques par board
        board_stats = db.session.query(
            Tickets.board_name,
            func.count(TicketAnalysisHistory.id).label('total_analyses')
        ).join(TicketAnalysisHistory, Tickets.id_ticket == TicketAnalysisHistory.ticket_id)\
         .group_by(Tickets.board_name).all()
        
        board_list = []
        for board_name, total in board_stats:
            # Calculer les réanalyses pour ce board spécifique
            board_reanalyses = db.session.query(TicketAnalysisHistory).join(
                Tickets, TicketAnalysisHistory.ticket_id == Tickets.id_ticket
            ).join(
                AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
            ).join(
                Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
            ).filter(
                Tickets.board_name == board_name,
                Analyse.reanalyse == True
            ).count()
            
            board_list.append({
                'board_name': board_name,
                'total_analyses': total,
                'reanalyses': board_reanalyses,
                'initial_analyses': total - board_reanalyses
            })
        
        return jsonify({
            "status": "success",
            "statistics": {
                "total_tickets": total_tickets,
                "total_analyses": total_analyses,
                "initial_analyses": total_initial_analyses,
                "reanalyses": total_reanalyses,
                "reanalysis_rate": round((total_reanalyses / total_analyses * 100), 2) if total_analyses > 0 else 0,
                "criticality_distribution": criticality_stats,
                "by_board": board_list
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur lors de la récupération des statistiques: {str(e)}"}), 500


@trello_bp.route('/api/trello/config-board-subscription/<int:config_id>/target-list', methods=['POST'])
def set_target_list(config_id):
    """
    Définit la liste cible pour le déplacement automatique des cartes après analyse.
    
    Body JSON attendu:
    {
        "targetListId": "string",
        "targetListName": "string"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "error",
                "message": "Corps de requête JSON requis"
            }), 400
        
        target_list_id = data.get('targetListId')
        target_list_name = data.get('targetListName', 'Liste cible')
        
        if not target_list_id:
            return jsonify({
                "status": "error",
                "message": "targetListId requis"
            }), 400
        
        # Récupérer la configuration
        config = Config.query.get(config_id)
        if not config:
            return jsonify({
                "status": "error",
                "message": f"Configuration avec l'ID {config_id} introuvable"
            }), 404
        
        # Mettre à jour avec la liste cible
        config_data = config.config_data.copy()
        config_data['targetListId'] = target_list_id
        config_data['targetListName'] = target_list_name
        
        config.config_data = config_data
        config.updatedAt = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Liste cible '{target_list_name}' configurée avec succès",
            "data": {
                "config_id": config_id,
                "targetListId": target_list_id,
                "targetListName": target_list_name
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la configuration: {str(e)}"
        }), 500

    