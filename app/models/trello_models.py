"""
Modèle de données pour les cards Trello et leur analyse de criticité.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from app import db
import json


@dataclass
class TrelloCard:
    """Modèle de données pour une card Trello."""
    
    id: str
    name: str
    desc: str
    due: Optional[str]
    list_name: str
    board_id: str
    board_name: str
    labels: List[Dict[str, Any]]
    members: List[Dict[str, Any]]
    url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CriticalityAnalysis:
    """Modèle de données pour l'analyse de criticité d'une card."""
    
    card_id: str
    card_name: str
    criticality_level: str  # HIGH, MEDIUM, LOW
    analyzed_at: datetime
    board_id: str
    success: bool
    error: Optional[str] = None


@dataclass
class BoardAnalysisSummary:
    """Résumé de l'analyse de criticité pour un board."""
    
    board_id: str
    board_name: str
    total_cards: int
    high_criticality: int
    medium_criticality: int
    low_criticality: int
    analyzed_at: datetime
    success_rate: float


class Config(db.Model):
    __tablename__ = 'config'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_data = db.Column(db.JSON, nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Config {self.id}>'
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'trello_config': self.trello_config,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def get_trello_config_json(self):
        """Retourne la configuration Trello au format JSON string."""
        import json
        return json.dumps(self.trello_config, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data):
        """Crée un objet Config à partir d'un dictionnaire."""
        trello_config = {
            'token': data.get('token'),
            'boardId': data.get('boardId'),
            'boardName': data.get('boardName'),
            'listId': data.get('listId'),
            'listName': data.get('listName')
        }
        return cls(trello_config=trello_config)
    
    @classmethod
    def get_latest_config(cls):
        """Récupère la dernière configuration Trello."""
        return cls.query.order_by(cls.created_at.desc()).first()
    
    @classmethod
    def get_config_by_board(cls, board_id):
        """Récupère une configuration par board_id."""
        return cls.query.filter(cls.trello_config['boardId'].astext == board_id).first()
