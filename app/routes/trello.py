from flask import Blueprint, jsonify, request
import os
import html
import re
from datetime import datetime
from app.services.trello_service import get_trello_user_info
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.services.ticket_reanalysis_service import TicketReanalysisService
from app.models.trello_models import TrelloCard, CriticalityAnalysis, BoardAnalysisSummary, Config, Analyse, AnalyseBoard, Tickets
from app import db
from app.utils.crypto_service import crypto_service
from app.services.database_service import DatabaseService
from sqlalchemy import func
import requests
import traceback


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
            
            response = requests.get(cards_url, params=params)
            response.raise_for_status()
            cards_data = response.json()
            
        except requests.exceptions.RequestException as e:
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
            # Préparer les données de la carte pour l'analyse
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
            
            # Analyser la criticité
            result = analyzer.analyze_card_criticality(card_data)
            result['analyzed_at'] = datetime.now().isoformat()
            analysis_results.append(result)
            
            # Si analyse_board_id est fourni, sauvegarder dans la table tickets
            if analyse_board_id and result.get('success', False):
                try:
                    # Vérifier si le ticket existe déjà
                    if not Tickets.exists_by_trello_id(card['id']):
                        ticket = Tickets(
                            analyse_board_id=analyse_board_id,
                            trello_ticket_id=card['id'],
                            ticket_metadata={
                                'name': card['name'],
                                'desc': card.get('desc', ''),
                                'due': card.get('due'),
                                'url': card['url'],
                                'labels': card.get('labels', []),
                                'members': card.get('members', []),
                                'analysis_result': result
                            },
                            criticality_level=result.get('criticality_level', '').lower() if result.get('criticality_level') else None
                        )
                        
                        db.session.add(ticket)
                        saved_tickets.append({
                            'trello_ticket_id': card['id'],
                            'card_name': card['name'],
                            'criticality_level': ticket.criticality_level
                        })
                        
                except Exception as ticket_error:
                    print(f"Erreur lors de la sauvegarde du ticket {card['id']}: {str(ticket_error)}")
        
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


@trello_bp.route('/api/trello/cards/analyze', methods=['POST'])
def analyze_cards_criticality():
    """
    Analyse la criticité de plusieurs cards Trello.
    
    Body JSON attendu:
    {
        "board_id": "string",
        "board_name": "string", 
        "cards": [
            {
                "id": "string",
                "name": "string",
                "desc": "string",
                "due": "string|null",
                "list_name": "string",
                "labels": [...],
                "members": [...],
                "url": "string"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Corps de requête JSON requis"}), 400
        
        board_id = data.get('board_id')
        board_name = data.get('board_name', 'Board sans nom')
        cards_data = data.get('cards', [])
        
        if not board_id:
            return jsonify({"error": "board_id requis"}), 400
        
        if not cards_data:
            return jsonify({"error": "Liste de cards vide"}), 400
        
        # Initialiser l'analyseur de criticité
        analyzer = CriticalityAnalyzer()
        
        # Analyser chaque card
        analysis_results = []
        for card_data in cards_data:
            # Ajouter les informations du board à chaque card
            card_data['board_id'] = board_id
            card_data['board_name'] = board_name
            
            result = analyzer.analyze_card_criticality(card_data)
            result['analyzed_at'] = datetime.now().isoformat()
            analysis_results.append(result)
        
        # Calculer les statistiques du board
        total_cards = len(analysis_results)
        successful_analyses = [r for r in analysis_results if r.get('success', False)]
        
        criticality_counts = {
            'CRITICAL_TOTAL': len(successful_analyses),  # Tous les tickets analysés sont critiques
            'NON_CRITICAL': 0,  # Plus de tickets non-critiques
            'HIGH': len([r for r in successful_analyses if r['criticality_level'] == 'HIGH']),
            'MEDIUM': len([r for r in successful_analyses if r['criticality_level'] == 'MEDIUM']),
            'LOW': len([r for r in successful_analyses if r['criticality_level'] == 'LOW'])
        }
        
        success_rate = len(successful_analyses) / total_cards if total_cards > 0 else 0
        
        response = {
            "board_analysis": {
                "board_id": board_id,
                "board_name": board_name,
                "total_cards": total_cards,
                "criticality_distribution": criticality_counts,
                "success_rate": round(success_rate * 100, 2),
                "analyzed_at": datetime.now().isoformat()
            },
            "cards_analysis": analysis_results
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'analyse: {str(e)}"}), 500


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

        # Base query - always join with AnalyseBoard and Tickets to count tickets
        query = db.session.query(
            Analyse,
            func.count(Tickets.id_ticket).label('tickets_count')
        ).select_from(Analyse) \
         .outerjoin(AnalyseBoard, AnalyseBoard.analyse_id == Analyse.analyse_id) \
         .outerjoin(Tickets, Tickets.analyse_board_id == AnalyseBoard.id) \
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
                        query = query.having(func.count(Tickets.id_ticket) > value)
                    elif operator == 'gte':
                        query = query.having(func.count(Tickets.id_ticket) >= value)
                    elif operator == 'lt':
                        query = query.having(func.count(Tickets.id_ticket) < value)
                    elif operator == 'lte':
                        query = query.having(func.count(Tickets.id_ticket) <= value)
                    elif operator == 'eq':
                        query = query.having(func.count(Tickets.id_ticket) == value)
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

        # Récupérer l'analyse_board lié à analyse_id
        analyse_board = db.session.query(AnalyseBoard).filter_by(analyse_id=analyse_id).first()
        if not analyse_board:
            return jsonify({"status": "error", "message": "Aucun analyse_board trouvé pour cette analyse"}), 404

        query = db.session.query(Tickets).filter(Tickets.analyse_board_id == analyse_board.id)

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
            analysis_result = meta.get('analysis_result', {})

            # Nettoyage lisible du champ justification
            raw_justification = analysis_result.get('justification', '')
            try:
                justification = html.unescape(raw_justification).replace('\r', '').strip()
                justification = re.sub(r'\n{2,}', '\n', justification)
            except Exception:
                justification = raw_justification

            tickets_data.append({
                "name": meta.get('name'),
                "desc": meta.get('desc'),
                "due": meta.get('due'),
                "url": meta.get('url'),
                "criticality_level": ticket.criticality_level.upper() if ticket.criticality_level else None,
                "justification": justification,
                "analyzed_at": analysis_result.get('analyzed_at')
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


@trello_bp.route('/api/trello/ticket/<trello_ticket_id>/reanalyze', methods=['POST'])
def reanalyze_ticket(trello_ticket_id):
    """
    Réanalyse un ticket spécifique en créant TOUJOURS une nouvelle analyse, analyse_board et ticket.
    Permet plusieurs réanalyses du même ticket avec des noms incrémentés (reanalyse_1, reanalyse_2, etc.).
    
    Body JSON (optionnel):
    {
        "config_id": integer  // ID de la configuration à utiliser (optionnel, utilise la dernière si non fourni)
    }
    
    Response:
    {
        "success": boolean,
        "analysis": {...},      // Détails de la nouvelle analyse créée
        "analysis_board": {...}, // Détails de l'analyse_board créée  
        "ticket": {...},        // Détails du nouveau ticket créé
        "criticality_analysis": {...}, // Résultat de l'analyse IA
        "config_used": {...},   // Configuration utilisée
        "reanalysis_info": {...} // Informations sur la réanalyse
    }
    """
    try:
        data = request.get_json() or {}
        config_id = data.get('config_id')
        
        # Récupérer la configuration
        if config_id:
            config = Config.query.get(config_id)
        else:
            config = Config.get_latest_config()
            
        if not config:
            return jsonify({
                "success": False,
                "error": "Aucune configuration trouvée",
                "error_code": "NO_CONFIG"
            }), 404
        
        config_data = config.config_data
        token = config_data.get('token')
        
        if not token:
            return jsonify({
                "success": False,
                "error": "Token Trello manquant dans la configuration",
                "error_code": "NO_TOKEN"
            }), 400
        
        # Compter les analyses existantes pour ce ticket
        existing_analyses = Tickets.query.filter(
            Tickets.trello_ticket_id.like(f"{trello_ticket_id}%")
        ).count()
        reanalysis_number = existing_analyses + 1
        is_reanalysis = existing_analyses > 0
        
        # Récupérer les données du ticket depuis Trello OU créer des données de test
        card_data = None
        try:
            card_url = f"https://api.trello.com/1/cards/{trello_ticket_id}"
            params = {
                'key': os.environ.get('TRELLO_API_KEY'),
                'token': token,
                'fields': 'id,name,desc,due,url,dateLastActivity,idBoard,idList',
                'board': 'true',
                'list': 'true'
            }
            
            response = requests.get(card_url, params=params)
            response.raise_for_status()
            card_data = response.json()
            
        except requests.exceptions.RequestException as e:
            # Si le ticket n'existe pas sur Trello (cas de test), créer des données fictives
            print(f"⚠️ Ticket non trouvé sur Trello, création de données de test: {str(e)}")
            card_data = {
                'id': trello_ticket_id,
                'name': f"Ticket Test {trello_ticket_id}",
                'desc': "Description de test pour la réanalyse",
                'due': None,
                'url': f"https://trello.com/c/{trello_ticket_id}",
                'board': {
                    'id': config_data.get('boardId', 'TEST_BOARD'),
                    'name': config_data.get('boardName', 'Board de Test')
                },
                'list': {
                    'id': config_data.get('listId', 'TEST_LIST'),
                    'name': config_data.get('listName', 'Liste de Test')
                },
                'labels': [],
                'members': []
            }
        
        # Créer le nom du ticket avec comptage
        original_name = card_data['name']
        if is_reanalysis:
            ticket_name = f"{original_name} - reanalyse_{reanalysis_number}"
        else:
            ticket_name = f"{original_name} - reanalyse_1"
        
        # 1. Créer une nouvelle analyse
        analysis_reference = f"analyse_{trello_ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{reanalysis_number}"
        new_analysis = Analyse(reference=analysis_reference)
        db.session.add(new_analysis)
        db.session.flush()  # Pour obtenir l'ID
        
        # 2. Créer une nouvelle analyse_board
        new_analysis_board = AnalyseBoard(
            analyse_id=new_analysis.analyse_id,
            platform="trello"
        )
        db.session.add(new_analysis_board)
        db.session.flush()  # Pour obtenir l'ID
        
        # 3. Préparer les données pour l'analyse IA
        trello_card_data = {
            'id': card_data['id'],
            'name': ticket_name,  # Utiliser le nom avec comptage
            'desc': card_data.get('desc', ''),
            'due': card_data.get('due'),
            'list_name': card_data.get('list', {}).get('name', 'Liste inconnue'),
            'board_id': card_data.get('board', {}).get('id', config_data.get('boardId', '')),
            'board_name': card_data.get('board', {}).get('name', config_data.get('boardName', '')),
            'labels': card_data.get('labels', []),
            'members': card_data.get('members', []),
            'url': card_data['url']
        }
        
        # 4. Analyser la criticité avec l'IA
        analyzer = CriticalityAnalyzer()
        criticality_result = analyzer.analyze_card_criticality(trello_card_data)
        
        # 5. Créer un nouveau ticket avec un ID unique
        ticket_metadata = {
            'name': ticket_name,
            'original_name': original_name,
            'desc': card_data.get('desc', ''),
            'due': card_data.get('due'),
            'url': card_data['url'],
            'labels': card_data.get('labels', []),
            'members': card_data.get('members', []),
            'board_info': {
                'board_id': card_data.get('board', {}).get('id'),
                'board_name': card_data.get('board', {}).get('name'),
                'list_id': card_data.get('list', {}).get('id'),
                'list_name': card_data.get('list', {}).get('name')
            },
            'reanalysis_info': {
                'is_reanalysis': is_reanalysis,
                'reanalysis_number': reanalysis_number,
                'original_trello_id': trello_ticket_id,
                'analysis_reference': analysis_reference,
                'analyzed_at': datetime.now().isoformat()
            },
            'criticality_analysis': criticality_result
        }
        
        # Créer un ID de ticket unique en ajoutant un suffixe au trello_ticket_id original
        unique_ticket_id = f"{trello_ticket_id}_reanalyse_{reanalysis_number}"
        
        new_ticket = Tickets(
            analyse_board_id=new_analysis_board.id,
            trello_ticket_id=unique_ticket_id,  # ID unique pour éviter les conflits
            ticket_metadata=ticket_metadata,
            criticality_level=criticality_result.get('criticality_level', '').lower() if criticality_result.get('success', False) else None
        )
        
        db.session.add(new_ticket)
        db.session.flush()  # Pour obtenir l'ID
        
        # Commit toutes les modifications
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Réanalyse #{reanalysis_number} créée avec succès pour le ticket {trello_ticket_id}",
            "analysis": new_analysis.to_dict(),
            "analysis_board": new_analysis_board.to_dict(),
            "ticket": new_ticket.to_dict(),
            "criticality_analysis": criticality_result,
            "config_used": config.to_dict(),
            "reanalysis_info": {
                "is_reanalysis": is_reanalysis,
                "reanalysis_number": reanalysis_number,
                "original_trello_id": trello_ticket_id,
                "unique_ticket_id": unique_ticket_id,
                "ticket_name": ticket_name,
                "original_name": original_name,
                "total_analyses": reanalysis_number,
                "new_ticket_id": new_ticket.id_ticket
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la réanalyse: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }), 500


@trello_bp.route('/api/trello/ticket/<trello_ticket_id>/reanalysis-history', methods=['GET'])
def get_reanalysis_history(trello_ticket_id):
    """
    Récupère l'historique de toutes les réanalyses d'un ticket spécifique.
    
    Response:
    {
        "success": boolean,
        "original_trello_id": string,
        "total_reanalyses": integer,
        "reanalyses": [
            {
                "ticket": {...},
                "analysis": {...},
                "analysis_board": {...},
                "reanalysis_number": integer
            }
        ]
    }
    """
    try:
        # Rechercher tous les tickets liés à ce trello_ticket_id
        # Ils peuvent avoir des IDs comme "ABC123_reanalyse_1", "ABC123_reanalyse_2", etc.
        tickets = Tickets.query.filter(
            Tickets.trello_ticket_id.like(f"{trello_ticket_id}%")
        ).order_by(Tickets.createdAt.desc()).all()
        
        if not tickets:
            return jsonify({
                "success": True,
                "original_trello_id": trello_ticket_id,
                "total_reanalyses": 0,
                "reanalyses": [],
                "message": "Aucune réanalyse trouvée pour ce ticket"
            }), 200
        
        reanalyses_details = []
        
        for ticket in tickets:
            # Récupérer les détails de l'analyse et analyse_board
            analysis_board = AnalyseBoard.query.get(ticket.analyse_board_id)
            analysis = Analyse.query.get(analysis_board.analyse_id) if analysis_board else None
            
            # Extraire le numéro de réanalyse des métadonnées
            reanalysis_info = ticket.ticket_metadata.get('reanalysis_info', {}) if ticket.ticket_metadata else {}
            reanalysis_number = reanalysis_info.get('reanalysis_number', 1)
            
            reanalysis_detail = {
                "ticket": ticket.to_dict(),
                "analysis": analysis.to_dict() if analysis else None,
                "analysis_board": analysis_board.to_dict() if analysis_board else None,
                "reanalysis_number": reanalysis_number,
                "ticket_name": ticket.ticket_metadata.get('name') if ticket.ticket_metadata else None,
                "original_name": ticket.ticket_metadata.get('original_name') if ticket.ticket_metadata else None
            }
            
            reanalyses_details.append(reanalysis_detail)
        
        return jsonify({
            "success": True,
            "original_trello_id": trello_ticket_id,
            "total_reanalyses": len(tickets),
            "reanalyses": reanalyses_details
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la récupération de l'historique: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }), 500


@trello_bp.route('/api/trello/ticket/<trello_ticket_id>/stats', methods=['GET'])
def get_ticket_detailed_stats(trello_ticket_id):
    """
    Récupère les statistiques détaillées et complètes d'un ticket spécifique avec tous ses détails.
    
    URL: /api/trello/ticket/{trello_ticket_id}/stats
    
    Response:
    {
        "success": boolean,
        "original_trello_id": "dhzADbj5",
        "total_reanalyses": 3,
        "summary": {
            "first_analysis_date": "2025-07-29T10:30:00",
            "last_analysis_date": "2025-07-30T15:45:00",
            "criticality_distribution": {
                "high": 1,
                "medium": 2,
                "low": 0
            },
            "latest_criticality": "medium"
        },
        "detailed_reanalyses": [
            {
                "ticket_id": "dhzADbj5_reanalyse_1",
                "internal_id": 123,
                "name": "Ticket Test - reanalyse_1",
                "description": "Description complète du ticket...",
                "criticality_level": "high",
                "created_at": "2025-07-29T10:30:00",
                "updated_at": "2025-07-29T10:30:00",
                "reanalysis_number": 1,
                "board_info": {...},
                "analysis_reference": "analyse_dhzADbj5_20250729_1030_1",
                "full_metadata": {...}
            }
        ]
    }
    """
    try:
        # Rechercher tous les tickets liés à ce trello_ticket_id
        # Format possible: "dhzADbj5", "dhzADbj5_reanalyse_1", "dhzADbj5_reanalyse_2", etc.
        tickets = Tickets.query.filter(
            Tickets.trello_ticket_id.like(f"{trello_ticket_id}%")
        ).order_by(Tickets.createdAt.asc()).all()
        
        if not tickets:
            return jsonify({
                "success": True,
                "original_trello_id": trello_ticket_id,
                "total_reanalyses": 0,
                "message": "Aucune réanalyse trouvée pour ce ticket",
                "summary": {
                    "first_analysis_date": None,
                    "last_analysis_date": None,
                    "criticality_distribution": {"high": 0, "medium": 0, "low": 0},
                    "latest_criticality": None
                },
                "detailed_reanalyses": []
            }), 200
        
        # Préparer les détails de chaque réanalyse
        detailed_reanalyses = []
        criticality_counts = {"high": 0, "medium": 0, "low": 0}
        latest_criticality = None
        
        for ticket in tickets:
            # Récupérer les détails de l'analyse et analyse_board
            analysis_board = AnalyseBoard.query.get(ticket.analyse_board_id)
            analysis = Analyse.query.get(analysis_board.analyse_id) if analysis_board else None
            
            # Extraire les métadonnées du ticket
            metadata = ticket.ticket_metadata or {}
            reanalysis_info = metadata.get('reanalysis_info', {})
            board_info = metadata.get('board_info', {})
            criticality_analysis = metadata.get('criticality_analysis', {})
            
            # Compter les criticités
            if ticket.criticality_level:
                criticality_counts[ticket.criticality_level] += 1
                latest_criticality = ticket.criticality_level
            
            # Construire les détails de cette réanalyse
            reanalysis_detail = {
                "ticket_id": ticket.trello_ticket_id,
                "internal_id": ticket.id_ticket,
                "name": metadata.get('name', 'Nom non disponible'),
                "original_name": metadata.get('original_name', 'Nom original non disponible'),
                "description": metadata.get('desc', 'Description non disponible'),
                "criticality_level": ticket.criticality_level,
                "created_at": ticket.createdAt.isoformat() if ticket.createdAt else None,
                "updated_at": ticket.updatedAt.isoformat() if ticket.updatedAt else None,
                "reanalysis_number": reanalysis_info.get('reanalysis_number', 1),
                "is_reanalysis": reanalysis_info.get('is_reanalysis', False),
                "analysis_reference": reanalysis_info.get('analysis_reference', 'Non disponible'),
                "analyzed_at": reanalysis_info.get('analyzed_at', None),
                "url": metadata.get('url', 'URL non disponible'),
                "due_date": metadata.get('due', None),
                "labels": metadata.get('labels', []),
                "members": metadata.get('members', []),
                "board_info": {
                    "board_id": board_info.get('board_id', 'Non disponible'),
                    "board_name": board_info.get('board_name', 'Non disponible'),
                    "list_id": board_info.get('list_id', 'Non disponible'),
                    "list_name": board_info.get('list_name', 'Non disponible')
                },
                "analysis_info": {
                    "analysis_id": analysis.analyse_id if analysis else None,
                    "analysis_reference": analysis.reference if analysis else None,
                    "analysis_created_at": analysis.createdAt.isoformat() if analysis and analysis.createdAt else None,
                    "analysis_board_id": analysis_board.id if analysis_board else None,
                    "platform": analysis_board.platform if analysis_board else None
                },
                "criticality_analysis": {
                    "ai_success": criticality_analysis.get('success', False),
                    "ai_reasoning": criticality_analysis.get('reasoning', 'Non disponible'),
                    "ai_factors": criticality_analysis.get('factors', {}),
                    "ai_score": criticality_analysis.get('score', None)
                },
                "full_metadata": metadata  # Métadonnées complètes pour debug si besoin
            }
            
            detailed_reanalyses.append(reanalysis_detail)
        
        # Calculer le résumé
        summary = {
            "first_analysis_date": detailed_reanalyses[0]["created_at"] if detailed_reanalyses else None,
            "last_analysis_date": detailed_reanalyses[-1]["created_at"] if detailed_reanalyses else None,
            "criticality_distribution": criticality_counts,
            "latest_criticality": latest_criticality,
            "total_analyses": len(detailed_reanalyses),
            "has_descriptions": sum(1 for r in detailed_reanalyses if r["description"] != "Description non disponible"),
            "has_criticalities": sum(1 for r in detailed_reanalyses if r["criticality_level"] is not None),
            "analysis_success_rate": round(
                sum(1 for r in detailed_reanalyses if r["criticality_analysis"]["ai_success"]) / len(detailed_reanalyses) * 100, 2
            ) if detailed_reanalyses else 0
        }
        
        return jsonify({
            "success": True,
            "original_trello_id": trello_ticket_id,
            "total_reanalyses": len(tickets),
            "summary": summary,
            "detailed_reanalyses": detailed_reanalyses
        }), 200
        
    except Exception as e:
        import traceback
        print("❌ Erreur dans get_ticket_detailed_stats:")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la récupération des détails: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }), 500


@trello_bp.route('/api/trello/tickets/reanalysis-stats', methods=['POST'])
def get_tickets_reanalysis_stats():
    """
    Récupère les statistiques de réanalyse pour un ou plusieurs tickets.
    
    Body JSON:
    {
        "ticket_ids": ["trello_id_1", "trello_id_2", ...]  // Liste des IDs Trello à analyser
    }
    OU
    {
        "ticket_id": "trello_id_single"  // Pour un seul ticket
    }
    
    Response:
    {
        "success": boolean,
        "total_tickets_requested": integer,
        "tickets_found": integer,
        "tickets_stats": [
            {
                "original_trello_id": "ABC123",
                "total_reanalyses": 3,
                "first_analysis_date": "2024-01-15T10:30:00",
                "last_analysis_date": "2024-01-20T15:45:00",
                "criticality_levels": {
                    "high": 1,
                    "medium": 2,
                    "low": 0
                },
                "latest_criticality": "medium",
                "all_ticket_ids": [
                    "ABC123_reanalyse_1",
                    "ABC123_reanalyse_2", 
                    "ABC123_reanalyse_3"
                ]
            }
        ],
        "summary": {
            "total_reanalyses_all_tickets": 10,
            "avg_reanalyses_per_ticket": 2.5,
            "most_reanalyzed_ticket": {
                "trello_id": "ABC123",
                "count": 3
            }
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Body JSON requis",
                "error_code": "MISSING_BODY"
            }), 400
        
        # Récupérer la liste des ticket_ids à analyser
        ticket_ids = []
        if 'ticket_ids' in data:
            ticket_ids = data['ticket_ids']
            if not isinstance(ticket_ids, list):
                return jsonify({
                    "success": False,
                    "error": "ticket_ids doit être une liste",
                    "error_code": "INVALID_FORMAT"
                }), 400
        elif 'ticket_id' in data:
            ticket_ids = [data['ticket_id']]
        else:
            return jsonify({
                "success": False,
                "error": "ticket_ids ou ticket_id requis",
                "error_code": "MISSING_TICKET_IDS"
            }), 400
        
        if not ticket_ids:
            return jsonify({
                "success": False,
                "error": "Au moins un ticket_id requis",
                "error_code": "EMPTY_TICKET_IDS"
            }), 400
        
        tickets_stats = []
        total_reanalyses_all_tickets = 0
        tickets_found = 0
        most_reanalyzed_count = 0
        most_reanalyzed_ticket = None
        
        for trello_ticket_id in ticket_ids:
            # Rechercher tous les tickets liés à ce trello_ticket_id
            # Format: "ABC123_reanalyse_1", "ABC123_reanalyse_2", etc.
            tickets = Tickets.query.filter(
                Tickets.trello_ticket_id.like(f"{trello_ticket_id}%")
            ).order_by(Tickets.createdAt.asc()).all()
            
            if not tickets:
                # Ticket non trouvé, on l'ajoute quand même avec 0 réanalyses
                tickets_stats.append({
                    "original_trello_id": trello_ticket_id,
                    "total_reanalyses": 0,
                    "first_analysis_date": None,
                    "last_analysis_date": None,
                    "criticality_levels": {
                        "high": 0,
                        "medium": 0,
                        "low": 0
                    },
                    "latest_criticality": None,
                    "all_ticket_ids": [],
                    "status": "not_found"
                })
                continue
            
            tickets_found += 1
            total_reanalyses = len(tickets)
            total_reanalyses_all_tickets += total_reanalyses
            
            # Calculer les statistiques de criticité
            criticality_counts = {"high": 0, "medium": 0, "low": 0}
            latest_criticality = None
            all_ticket_ids = []
            
            for ticket in tickets:
                all_ticket_ids.append(ticket.trello_ticket_id)
                if ticket.criticality_level:
                    criticality_counts[ticket.criticality_level] += 1
                    # Le dernier ticket dans la liste (ordre croissant) a la criticité la plus récente
                    latest_criticality = ticket.criticality_level
            
            # Déterminer le ticket le plus réanalysé
            if total_reanalyses > most_reanalyzed_count:
                most_reanalyzed_count = total_reanalyses
                most_reanalyzed_ticket = trello_ticket_id
            
            ticket_stats = {
                "original_trello_id": trello_ticket_id,
                "total_reanalyses": total_reanalyses,
                "first_analysis_date": tickets[0].createdAt.isoformat() if tickets[0].createdAt else None,
                "last_analysis_date": tickets[-1].createdAt.isoformat() if tickets[-1].createdAt else None,
                "criticality_levels": criticality_counts,
                "latest_criticality": latest_criticality,
                "all_ticket_ids": all_ticket_ids,
                "status": "found"
            }
            
            tickets_stats.append(ticket_stats)
        
        # Calculer la moyenne de réanalyses par ticket (seulement pour les tickets trouvés)
        avg_reanalyses_per_ticket = (
            total_reanalyses_all_tickets / tickets_found 
            if tickets_found > 0 
            else 0
        )
        
        summary = {
            "total_reanalyses_all_tickets": total_reanalyses_all_tickets,
            "avg_reanalyses_per_ticket": round(avg_reanalyses_per_ticket, 2),
            "most_reanalyzed_ticket": {
                "trello_id": most_reanalyzed_ticket,
                "count": most_reanalyzed_count
            } if most_reanalyzed_ticket else None
        }
        
        return jsonify({
            "success": True,
            "total_tickets_requested": len(ticket_ids),
            "tickets_found": tickets_found,
            "tickets_stats": tickets_stats,
            "summary": summary
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la récupération des statistiques: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }), 500


@trello_bp.route('/api/trello/tickets/all-reanalysis-stats', methods=['GET'])
def get_all_tickets_reanalysis_stats():
    """
    Récupère les statistiques de réanalyse pour TOUS les tickets dans la base de données.
    Regroupe automatiquement les tickets par leur ID Trello original.
    
    Query parameters:
    - limit: Nombre maximum de tickets à retourner (défaut: 50)
    - offset: Décalage pour la pagination (défaut: 0)
    - sort_by: Critère de tri ('total_reanalyses', 'last_analysis', 'first_analysis') (défaut: 'total_reanalyses')
    - order: Ordre de tri ('desc' ou 'asc') (défaut: 'desc')
    
    Response:
    {
        "success": boolean,
        "total_unique_tickets": integer,
        "returned_tickets": integer,
        "pagination": {...},
        "tickets_stats": [...],
        "global_summary": {...}
    }
    """
    try:
        # Paramètres de pagination et tri
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        sort_by = request.args.get('sort_by', 'total_reanalyses')
        order = request.args.get('order', 'desc')
        
        # Valider les paramètres
        if limit > 200:
            limit = 200  # Limite maximale pour éviter les surcharges
        
        valid_sort_fields = ['total_reanalyses', 'last_analysis', 'first_analysis']
        if sort_by not in valid_sort_fields:
            sort_by = 'total_reanalyses'
            
        if order not in ['asc', 'desc']:
            order = 'desc'
        
        # Récupérer tous les tickets et les regrouper par ID Trello original
        all_tickets = Tickets.query.order_by(Tickets.createdAt.asc()).all()
        
        # Regrouper par ID Trello original (extraire l'ID original des IDs avec suffixes)
        tickets_by_original_id = {}
        
        for ticket in all_tickets:
            trello_id = ticket.trello_ticket_id
            if not trello_id:
                continue
                
            # Extraire l'ID original (enlever le suffixe "_reanalyse_X")
            original_id = trello_id
            if '_reanalyse_' in trello_id:
                original_id = trello_id.split('_reanalyse_')[0]
            
            if original_id not in tickets_by_original_id:
                tickets_by_original_id[original_id] = []
            
            tickets_by_original_id[original_id].append(ticket)
        
        # Calculer les statistiques pour chaque groupe
        tickets_stats = []
        total_reanalyses_global = 0
        
        for original_id, ticket_group in tickets_by_original_id.items():
            # Trier les tickets par date de création
            sorted_tickets = sorted(ticket_group, key=lambda t: t.createdAt or datetime.min)
            
            total_reanalyses = len(sorted_tickets)
            total_reanalyses_global += total_reanalyses
            
            # Calculer les statistiques de criticité
            criticality_counts = {"high": 0, "medium": 0, "low": 0}
            latest_criticality = None
            all_ticket_ids = []
            
            for ticket in sorted_tickets:
                all_ticket_ids.append(ticket.trello_ticket_id)
                if ticket.criticality_level:
                    criticality_counts[ticket.criticality_level] += 1
                    latest_criticality = ticket.criticality_level
            
            ticket_stats = {
                "original_trello_id": original_id,
                "total_reanalyses": total_reanalyses,
                "first_analysis_date": sorted_tickets[0].createdAt.isoformat() if sorted_tickets[0].createdAt else None,
                "last_analysis_date": sorted_tickets[-1].createdAt.isoformat() if sorted_tickets[-1].createdAt else None,
                "criticality_levels": criticality_counts,
                "latest_criticality": latest_criticality,
                "all_ticket_ids": all_ticket_ids
            }
            
            tickets_stats.append(ticket_stats)
        
        # Trier les résultats
        reverse_order = (order == 'desc')
        
        if sort_by == 'total_reanalyses':
            tickets_stats.sort(key=lambda x: x['total_reanalyses'], reverse=reverse_order)
        elif sort_by == 'last_analysis':
            tickets_stats.sort(
                key=lambda x: x['last_analysis_date'] or '1900-01-01T00:00:00', 
                reverse=reverse_order
            )
        elif sort_by == 'first_analysis':
            tickets_stats.sort(
                key=lambda x: x['first_analysis_date'] or '1900-01-01T00:00:00', 
                reverse=reverse_order
            )
        
        # Pagination
        total_unique_tickets = len(tickets_stats)
        paginated_stats = tickets_stats[offset:offset + limit]
        
        # Calculer le résumé global
        if tickets_stats:
            avg_reanalyses = total_reanalyses_global / len(tickets_stats)
            most_reanalyzed = max(tickets_stats, key=lambda x: x['total_reanalyses'])
            
            global_summary = {
                "total_reanalyses_all_tickets": total_reanalyses_global,
                "avg_reanalyses_per_ticket": round(avg_reanalyses, 2),
                "most_reanalyzed_ticket": {
                    "trello_id": most_reanalyzed['original_trello_id'],
                    "count": most_reanalyzed['total_reanalyses']
                },
                "total_unique_original_tickets": len(tickets_stats),
                "criticality_distribution": {
                    "high": sum(stats['criticality_levels']['high'] for stats in tickets_stats),
                    "medium": sum(stats['criticality_levels']['medium'] for stats in tickets_stats),
                    "low": sum(stats['criticality_levels']['low'] for stats in tickets_stats)
                }
            }
        else:
            global_summary = {
                "total_reanalyses_all_tickets": 0,
                "avg_reanalyses_per_ticket": 0,
                "most_reanalyzed_ticket": None,
                "total_unique_original_tickets": 0,
                "criticality_distribution": {"high": 0, "medium": 0, "low": 0}
            }
        
        pagination_info = {
            "limit": limit,
            "offset": offset,
            "total_items": total_unique_tickets,
            "returned_items": len(paginated_stats),
            "has_next": (offset + limit) < total_unique_tickets,
            "has_prev": offset > 0,
            "next_offset": offset + limit if (offset + limit) < total_unique_tickets else None,
            "prev_offset": max(0, offset - limit) if offset > 0 else None
        }
        
        return jsonify({
            "success": True,
            "total_unique_tickets": total_unique_tickets,
            "returned_tickets": len(paginated_stats),
            "pagination": pagination_info,
            "sort": {
                "sort_by": sort_by,
                "order": order
            },
            "tickets_stats": paginated_stats,
            "global_summary": global_summary
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Erreur lors de la récupération des statistiques globales: {str(e)}",
            "error_code": "INTERNAL_ERROR"
        }), 500

