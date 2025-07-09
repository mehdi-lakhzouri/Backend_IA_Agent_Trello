from flask import Blueprint, jsonify, request
import os
from datetime import datetime
from app.services.trello_service import get_trello_user_info
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.models.trello_models import TrelloCard, CriticalityAnalysis, BoardAnalysisSummary, Config
from app import db
from app.utils.crypto_service import crypto_service


trello_bp = Blueprint('trello', __name__)

# Note: Les routes de connexion Trello sont maintenant gérées côté frontend

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


@trello_bp.route('/api/trello/health', methods=['GET'])
def trello_health_check():
    """
    Vérifie que le service d'analyse de criticité est opérationnel.
    """
    try:
        # Vérifier la configuration Gemini
        google_api_key = os.environ.get('GOOGLE_API_KEY')
        
        if not google_api_key:
            return jsonify({
                "status": "error",
                "message": "GOOGLE_API_KEY non configurée"
            }), 500
        
        # Test basique de l'analyseur
        analyzer = CriticalityAnalyzer()
        
        return jsonify({
            "status": "healthy",
            "service": "Trello Criticality Analyzer",
            "gemini_configured": True,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Erreur de service: {str(e)}"
        }), 500


@trello_bp.route('/api/trello/config-board-subscription', methods=['POST'])
def config_board_subscription():
    """
    Capture et enregistre la configuration d'abonnement aux boards Trello.
    Attend: trello_token, board_id et board_name
    """
    try:
        # Capturer les données envoyées par le frontend
        data = request.get_json()
        
        # Log des données reçues (pour debug)
        print(f"[DEBUG] Données reçues sur /api/trello/config-board-subscription: {data}")
        
        # Vérification basique
        if not data:
            return jsonify({
                "status": "error",
                "message": "Corps de requête JSON requis"
            }), 400
        
        # Extraire les champs requis
        trello_token = data.get('trello_token')
        board_id = data.get('board_id')
        board_name = data.get('board_name')
        
        # Vérification des champs obligatoires
        if not trello_token or not board_id or not board_name:
            return jsonify({
                "status": "error",
                "message": "trello_token, board_id et board_name sont requis"
            }), 400
        
        # Crypter le token avant l'enregistrement
        try:
            encrypted_token = crypto_service.encrypt_token(trello_token)
        except Exception as crypto_error:
            return jsonify({
                "status": "error",
                "message": f"Erreur lors du cryptage du token: {str(crypto_error)}"
            }), 500
        
        # Vérifier si une configuration existe déjà pour ce board
        existing_config = Config.query.filter_by(board_id=board_id).first()
        
        if existing_config:
            # Mettre à jour la configuration existante
            existing_config.trello_token = encrypted_token
            existing_config.board_name = board_name
            action = "mise à jour"
        else:
            # Créer une nouvelle configuration
            new_config = Config(
                trello_token=encrypted_token,
                board_id=board_id,
                board_name=board_name
            )
            db.session.add(new_config)
            action = "création"
        
        # Sauvegarder en base
        db.session.commit()
        
        # Retourner une réponse de succès
        return jsonify({
            "status": "success",
            "message": f"Configuration d'abonnement {action} avec succès",
            "data": {
                "board_id": board_id,
                "board_name": board_name,
                "action": action
            },
            "timestamp": datetime.now().isoformat(),
            "endpoint": "/api/trello/config-board-subscription"
        }), 200
        
    except Exception as e:
        # Rollback en cas d'erreur
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de l'enregistrement: {str(e)}"
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
                "board_id": config.board_id,
                "board_name": config.board_name,
                "created_at": config.created_at.isoformat() if config.created_at else None
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


@trello_bp.route('/api/trello/config-board-subscription/<board_id>', methods=['DELETE'])
def delete_board_subscription(board_id):
    """
    Supprime une configuration d'abonnement pour un board spécifique.
    """
    try:
        config = Config.query.filter_by(board_id=board_id).first()
        
        if not config:
            return jsonify({
                "status": "error",
                "message": f"Configuration non trouvée pour le board {board_id}"
            }), 404
        
        db.session.delete(config)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Configuration supprimée pour le board {board_id}"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Erreur lors de la suppression: {str(e)}"
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