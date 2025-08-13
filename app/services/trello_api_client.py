"""Thin wrapper around Trello REST endpoints used in the project."""
from __future__ import annotations
import os
import requests
from typing import Any, Dict, List

TRELLO_BASE = "https://api.trello.com/1"


class TrelloApiError(Exception):
    pass


class TrelloApiClient:
    def __init__(self, token: str, api_key: str | None = None):
        self.token = token
        self.api_key = api_key or os.environ.get("TRELLO_API_KEY")
        if not self.api_key:
            raise ValueError("TRELLO_API_KEY missing in environment")

    def _auth_params(self) -> Dict[str, Any]:
        return {"key": self.api_key, "token": self.token}

    def get_list_cards(self, list_id: str) -> List[Dict[str, Any]]:
        url = f"{TRELLO_BASE}/lists/{list_id}/cards"
        params = {
            **self._auth_params(),
            "fields": "id,name,desc,due,url,dateLastActivity",
            "attachments": "false",
            "members": "true",
            "labels": "true",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            raise TrelloApiError(f"Error fetching list cards: {e}") from e

    def add_label(self, card_id: str, board_id: str, criticality_level: str):  # pragma: no cover
        from tools.add_etiquette_tool import apply_criticality_label_with_creation
        return apply_criticality_label_with_creation(card_id=card_id, board_id=board_id, token=self.token, criticality_level=criticality_level)

    def add_comment(self, card_id: str, comment: str):  # pragma: no cover
        from tools.add_comment_tool import add_comment_to_card
        return add_comment_to_card(card_id=card_id, token=self.token, comment=comment)

    def move_card(self, card_id: str, new_list_id: str):  # pragma: no cover
        from tools.move_card_tool import move_card_to_list
        return move_card_to_list(card_id=card_id, new_list_id=new_list_id, token=self.token)
