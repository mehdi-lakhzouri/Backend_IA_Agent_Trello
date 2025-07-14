from flask import Blueprint, jsonify, request
import os
from datetime import datetime
from app.services.trello_service import get_trello_user_info
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.models.trello_models import TrelloCard, CriticalityAnalysis, BoardAnalysisSummary, Config, Analyse, AnalyseBoard, Tickets
from app import db
from app.utils.crypto_service import crypto_service
from app.services.database_service import DatabaseService
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
        critical_cards = [r for r in successful_analyses if r.get('is_critical', False)]
        
        criticality_counts = {
            'CRITICAL_TOTAL': len(critical_cards),
            'NON_CRITICAL': len([r for r in successful_analyses if not r.get('is_critical', True)]),
            'HIGH': len([r for r in critical_cards if r.get('criticality_level') == 'HIGH']),
            'MEDIUM': len([r for r in critical_cards if r.get('criticality_level') == 'MEDIUM']),
            'LOW': len([r for r in critical_cards if r.get('criticality_level') == 'LOW'])
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
        critical_cards = [r for r in successful_analyses if r.get('is_critical', False)]
        
        criticality_counts = {
            'CRITICAL_TOTAL': len(critical_cards),
            'NON_CRITICAL': len([r for r in successful_analyses if not r.get('is_critical', True)]),
            'HIGH': len([r for r in critical_cards if r['criticality_level'] == 'HIGH']),
            'MEDIUM': len([r for r in critical_cards if r['criticality_level'] == 'MEDIUM']),
            'LOW': len([r for r in critical_cards if r['criticality_level'] == 'LOW'])
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