"""
Modèle de données pour les cards Trello et leur analyse de criticité.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from app import db


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
    id = db.Column(db.Integer, primary_key=True)
    trello_token = db.Column(db.String(255), nullable=False)
    board_id = db.Column(db.String(255), nullable=False)
    board_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
