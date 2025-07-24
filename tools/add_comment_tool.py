import os
import requests
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

    # Correct Trello API endpoint for adding comments
    url = f"https://api.trello.com/1/cards/{card_id}/actions/comments"
    data = {
        'key': api_key,
        'token': token,
        'text': comment
    }

    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()

