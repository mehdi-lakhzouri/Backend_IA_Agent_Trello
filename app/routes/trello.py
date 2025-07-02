from flask import Blueprint, jsonify, request
import os
from app.services.trello_service import get_trello_user_info


trello_bp = Blueprint('trello', __name__)

@trello_bp.route('/api/trello/login', methods=['GET'])
def trello_login():
    trello_key = os.environ.get('TRELLO_API_KEY')
    app_name = os.environ.get('TRELLO_APP_NAME')
    params = {
        "expiration": "never",
        "name": app_name,
        "scope": "read,write",
        "response_type": "token",
        "key": trello_key
    }
    base_url = "https://trello.com/1/authorize"
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    auth_url = f"{base_url}?{query}"
    return jsonify({"auth_url": auth_url})

@trello_bp.route('/api/trello/use-token', methods=['POST'])
def trello_use_token():
    data = request.get_json()
    token = data.get('token')
    if not token:
        return jsonify({"error": "Token manquant"}), 400
    trello_key = os.environ.get('TRELLO_API_KEY')
    user_info = get_trello_user_info(trello_key, token)
    if "error" in user_info:
        return jsonify(user_info), 401
    return jsonify(user_info) 