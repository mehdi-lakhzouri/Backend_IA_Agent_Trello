from flask import Blueprint, jsonify, request
import os
from datetime import datetime
from app.services.trello_service import get_trello_user_info
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.models.trello_models import TrelloCard, CriticalityAnalysis, BoardAnalysisSummary, Config, Analyse, AnalyseBoard, Tickets
from app import db
from app.utils.crypto_service import crypto_service
from app.services.database_service import DatabaseService
from sqlalchemy import func
import requests


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
'''
@trello_bp.route('/api/analyses', methods=['GET'])
def get_analyses():
    """
    Récupère la liste de toutes les analyses présentes dans la table analyse.
    
    Query Parameters:
    - limit (int, optional): Nombre maximum d'analyses à retourner (défaut: 50)
    - offset (int, optional): Décalage pour la pagination (défaut: 0)
    
    Response:
    {
        "status": "success",
        "data": [
            {
                
                "reference": "string",
                "createdAt": "datetime",
                "tickets_count": integer
            },
            ...
        ],
        "total": integer,
        "count": integer,
        "limit": integer,
        "offset": integer
    }
    """
    try:
        # Récupération des paramètres de query
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validation des paramètres
        if limit < 1 or limit > 100:
            limit = 50
        if offset < 0:
            offset = 0
        
        # Requête pour récupérer les analyses avec pagination
        analyses_query = Analyse.query.order_by(Analyse.createdAt.desc())
        total_count = analyses_query.count()
        
        analyses = analyses_query.offset(offset).limit(limit).all()
        
        # Conversion en dictionnaire avec le nombre de tickets
        analyses_data = []
        for analyse in analyses:
            analyse_dict = analyse.to_dict()
            
            # Calculer le nombre total de tickets pour cette analyse
            tickets_count = 0
            for board in analyse.boards:
                tickets_count += len(board.tickets)
            
            analyse_dict['tickets_count'] = tickets_count
            analyses_data.append(analyse_dict)
        
        response = {
            "status": "success",
            "data": analyses_data,
            "total": total_count,
            "count": len(analyses_data),
            "limit": limit,
            "offset": offset
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la récupération des analyses: {str(e)}"
        }), 500'''

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
        # 1. Récupération des paramètres
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('perPage', 5, type=int)
        filters = request.args.getlist('filters[]')
        order_by = request.args.get('orderBy', 'createdAt', type=str)
        order_direction = request.args.get('orderDirection', 'desc', type=str)

        # 2. Validation des paramètres
        per_page = per_page if per_page in {5, 10, 15} else 10
        order_by = order_by if order_by in {'createdAt', 'tickets_count'} else 'createdAt'
        order_direction = order_direction if order_direction in {'asc', 'desc'} else 'desc'

        # 3. Construction de la requête de base
        if order_by == 'tickets_count':
            # Pour le tri par nombre de tickets, on fait un join avec sous-requête
            query = db.session.query(
                Analyse,
                func.count(Tickets.id_ticket).label('tickets_count')
            ).outerjoin(AnalyseBoard).outerjoin(Tickets).group_by(Analyse.analyse_id)
        else:
            # Pour les autres tris, requête simple
            query = Analyse.query

        # 4. Application des filtres
        applied_filters = []
        for f in filters:
            try:
                field, operator, value = f.split(':')
                
                if field == 'createdAt':
                    value = datetime.strptime(value, '%Y-%m-%d').date()
                    
                    # Appliquer le filtre selon l'opérateur
                    if operator == 'gte':
                        filter_cond = Analyse.createdAt >= value
                    elif operator == 'lte':
                        filter_cond = Analyse.createdAt <= value
                    elif operator == 'eq':
                        filter_cond = func.date(Analyse.createdAt) == value
                    elif operator == 'gt':
                        filter_cond = Analyse.createdAt > value
                    elif operator == 'lt':
                        filter_cond = Analyse.createdAt < value
                    else:
                        continue  # Opérateur non supporté
                    
                    query = query.filter(filter_cond)
                    applied_filters.append({"field": field, "operator": operator, "value": str(value)})
                    
                elif field == 'tickets_count':
                    value = int(value)
                    
                    # Pour le filtre par nombre de tickets, on doit utiliser HAVING
                    if order_by != 'tickets_count':
                        # Reconstruire la requête avec le count
                        query = db.session.query(
                            Analyse,
                            func.count(Tickets.id_ticket).label('tickets_count')
                        ).outerjoin(AnalyseBoard).outerjoin(Tickets).group_by(Analyse.analyse_id)
                    
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
                        continue  # Opérateur non supporté
                    
                    applied_filters.append({"field": field, "operator": operator, "value": value})
                    
            except Exception as filter_error:
                continue  # Ignore les filtres mal formatés

        # 5. Gestion du tri
        if order_by == 'tickets_count':
            sort_column = func.count(Tickets.id_ticket)
        else:
            sort_column = getattr(Analyse, order_by)

        query = query.order_by(
            sort_column.desc() if order_direction == 'desc' else sort_column.asc()
        )

        # 6. Pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # 7. Formatage des données
        analyses_data = []
        for item in pagination.items:
            if order_by == 'tickets_count' or any(f['field'] == 'tickets_count' for f in applied_filters):
                # Si on a fait une requête avec count, item est un tuple (Analyse, count)
                analysis = item[0] if isinstance(item, tuple) else item
                tickets_count = item[1] if isinstance(item, tuple) else 0
            else:
                # Sinon c'est un objet Analyse simple
                analysis = item
                # Calculer le nombre de tickets manuellement
                tickets_count = sum(len(board.tickets) for board in analysis.boards)
            
            analysis_dict = analysis.to_dict()
            analysis_dict['tickets_count'] = tickets_count
            analyses_data.append(analysis_dict)

        # 8. Réponse structurée
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
        return jsonify({
            "status": "error",
            "message": f"Erreur serveur: {str(e)}"
        }), 500