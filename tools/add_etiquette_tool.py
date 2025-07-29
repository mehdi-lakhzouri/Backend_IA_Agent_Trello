import os
import requests
from typing import Dict, Optional


def apply_criticality_label(card_id: str, board_id: str, token: str, criticality_level: str) -> Dict:
    """
    Apply a criticality label to a Trello card.

    Args:
        card_id (str): The ID of the Trello card.
        board_id (str): The ID of the Trello board.
        token (str): The Trello API token.
        criticality_level (str): The criticality level ("HIGH", "MEDIUM", "LOW").

    Returns:
        Dict: Response from the Trello API.
    """
    api_key = os.environ.get('TRELLO_API_KEY')
    if not api_key:
        raise ValueError("TRELLO_API_KEY environment variable is not set")
    
    label_name = f"Priority - {criticality_level.capitalize()}"

    url = f"https://api.trello.com/1/cards/{card_id}/idLabels"
    
    # Get existing labels for the board
    board_labels_url = f"https://api.trello.com/1/boards/{board_id}/labels"
    params = {
        'key': api_key,
        'token': token
    }
    
    response = requests.get(board_labels_url, params=params)
    response.raise_for_status()
    labels = response.json()

    # Find the label ID by name
    label_id = None
    for label in labels:
        if label['name'] == label_name:
            label_id = label['id']
            break

    if not label_id:
        raise ValueError(f"Label '{label_name}' not found on board '{board_id}'")

    # Apply label to the card
    params = {
        'key': api_key,
        'token': token,
        'value': label_id
    }

    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()


def create_criticality_label(board_id: str, token: str, criticality_level: str) -> Dict:
    """
    Create a criticality label on a Trello board.

    Args:
        board_id (str): The ID of the Trello board.
        token (str): The Trello API token.
        criticality_level (str): The criticality level ("HIGH", "MEDIUM", "LOW").

    Returns:
        Dict: Response from the Trello API containing the created label.
    """
    api_key = os.environ.get('TRELLO_API_KEY')
    if not api_key:
        raise ValueError("TRELLO_API_KEY environment variable is not set")
    
    # Map criticality levels to colors
    color_mapping = {
        'HIGH': 'red',
        'MEDIUM': 'orange',
        'LOW': 'green'
    }
    
    label_name = f"Priority - {criticality_level.capitalize()}"
    color = color_mapping.get(criticality_level.upper(), 'gray')
    
    url = "https://api.trello.com/1/labels"
    params = {
        'key': api_key,
        'token': token,
        'name': label_name,
        'color': color,
        'idBoard': board_id
    }
    
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()


def get_or_create_criticality_label(board_id: str, token: str, criticality_level: str) -> str:
    """
    Get the ID of a criticality label, creating it if it doesn't exist.

    Args:
        board_id (str): The ID of the Trello board.
        token (str): The Trello API token.
        criticality_level (str): The criticality level ("HIGH", "MEDIUM", "LOW").

    Returns:
        str: The ID of the label.
    """
    api_key = os.environ.get('TRELLO_API_KEY')
    if not api_key:
        raise ValueError("TRELLO_API_KEY environment variable is not set")
    
    label_name = f"Priority - {criticality_level.capitalize()}"
    
    # Get existing labels for the board
    board_labels_url = f"https://api.trello.com/1/boards/{board_id}/labels"
    params = {
        'key': api_key,
        'token': token
    }
    
    response = requests.get(board_labels_url, params=params)
    response.raise_for_status()
    labels = response.json()

    # Find the label ID by name
    for label in labels:
        if label['name'] == label_name:
            return label['id']
    
    # Label doesn't exist, create it
    created_label = create_criticality_label(board_id, token, criticality_level)
    return created_label['id']


def apply_criticality_label_with_creation(card_id: str, board_id: str, token: str, criticality_level: str) -> Dict:
    """
    Apply a criticality label to a Trello card, creating the label if it doesn't exist.

    Args:
        card_id (str): The ID of the Trello card.
        board_id (str): The ID of the Trello board.
        token (str): The Trello API token.
        criticality_level (str): The criticality level ("HIGH", "MEDIUM", "LOW").

    Returns:
        Dict: Response from the Trello API.
    """
    api_key = os.environ.get('TRELLO_API_KEY')
    if not api_key:
        raise ValueError("TRELLO_API_KEY environment variable is not set")

    # Définir les noms d'étiquettes de priorité possibles
    priority_labels = [
        "Priority - High",
        "Priority - Medium",
        "Priority - Low"
    ]

    # Récupérer les labels déjà appliqués à la carte
    card_labels_url = f"https://api.trello.com/1/cards/{card_id}/labels"
    params = {
        'key': api_key,
        'token': token
    }
    response = requests.get(card_labels_url, params=params)
    response.raise_for_status()
    card_labels = response.json()

    # Supprimer les anciennes étiquettes de priorité
    for label in card_labels:
        if label['name'] in priority_labels:
            delete_url = f"https://api.trello.com/1/cards/{card_id}/idLabels/{label['id']}"
            del_params = {
                'key': api_key,
                'token': token
            }
            del_resp = requests.delete(delete_url, params=del_params)
            del_resp.raise_for_status()

    # Get or create the label
    label_id = get_or_create_criticality_label(board_id, token, criticality_level)

    # Apply label to the card (correct endpoint)
    url = f"https://api.trello.com/1/cards/{card_id}/idLabels"
    params = {
        'key': api_key,
        'token': token,
        'value': label_id
    }

    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()
