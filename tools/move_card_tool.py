
import os
import requests
from typing import Dict

def move_card_to_list(card_id: str, new_list_id: str, token: str) -> Dict:
    """
    Déplace une carte Trello vers une autre liste.

    Args:
        card_id (str): L'ID de la carte Trello à déplacer.
        new_list_id (str): L'ID de la nouvelle liste.
        token (str): Le token Trello API.

    Returns:
        Dict: La réponse de l'API Trello.
    """
    api_key = os.environ.get('TRELLO_API_KEY')
    if not api_key:
        raise ValueError("TRELLO_API_KEY environment variable is not set")

    url = f"https://api.trello.com/1/cards/{card_id}/idList"
    params = {
        'key': api_key,
        'token': token,
        'value': new_list_id
    }

    response = requests.put(url, params=params)
    response.raise_for_status()
    return response.json()
