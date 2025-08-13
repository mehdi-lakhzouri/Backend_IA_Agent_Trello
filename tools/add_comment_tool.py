import os
import requests
import logging
from typing import Dict


def add_comment_to_card(card_id: str, token: str, comment: str) -> Dict:
    """
    Add a comment to a Trello card.

    Args:
        card_id (str): The ID of the Trello card.
        token (str): The Trello API token.
        comment (str): The comment text to add to the card.

    Returns:
        Dict: Response from the Trello API.
    """
    api_key = os.environ.get('TRELLO_API_KEY')
    if not api_key:
        raise ValueError("TRELLO_API_KEY environment variable is not set")

    logger = logging.getLogger('add_comment_tool')

    # URL pour l'ajout de commentaire sur une carte Trello
    url = f"https://api.trello.com/1/cards/{card_id}/actions/comments"

    # Paramètres de la requête (key et token dans params, text dans data)
    params = {
        'key': api_key,
        'token': token
    }
    # Préfixe personnalisé
    prefix = '[TALAN AGENT 🤖] '
    data = {
        'text': f'{prefix}{comment}'
    }

    # Envoyer la requête POST avec params et data (conforme à la doc Trello)
    response = requests.post(url, params=params, data=data)
    response.raise_for_status()
    logger.info(f"Comment added to card {card_id}: {comment}")
    logger.debug(f"Trello response: {response.text}")
    return response.json()

