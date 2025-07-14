"""
Modèle de données pour les cards Trello et leur analyse de criticité.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from app import db
import json
from sqlalchemy.sql import func


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
    
    def __init__(self, config_data, createdAt=None):
        self.config_data = config_data
        self.createdAt = createdAt or datetime.utcnow()
    
    def __repr__(self):
        return f'<Config {self.id}>'
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'config_data': self.config_data,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None
        }
    
    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def get_config_data_json(self):
        """Retourne la configuration au format JSON string."""
        import json
        return json.dumps(self.config_data, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data):
        """Crée un objet Config à partir d'un dictionnaire."""
        config_data = {
            'token': data.get('token'),
            'boardId': data.get('boardId'),
            'boardName': data.get('boardName'),
            'listId': data.get('listId'),
            'listName': data.get('listName')
        }
        return cls(config_data=config_data)
    
    @classmethod
    def get_latest_config(cls):
        """Récupère la dernière configuration."""
        from sqlalchemy import desc
        return cls.query.order_by(desc(getattr(cls, 'createdAt'))).first()
    
    @classmethod
    def get_config_by_board(cls, board_id):
        """Récupère une configuration par board_id."""
        return cls.query.filter(cls.config_data['boardId'].astext == board_id).first()


class Analyse(db.Model):
    __tablename__ = 'analyse'
    analyse_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reference = db.Column(db.String(64), unique=True, nullable=False)
    config_id = db.Column(db.Integer, db.ForeignKey('config.id'), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, config_id, reference=None, createdAt=None):
        self.config_id = config_id
        if reference is None:
            # Génère une référence unique basée sur la date et l'heure
            self.reference = f"analyse_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
        else:
            self.reference = reference
        self.createdAt = createdAt or datetime.utcnow()


class AnalyseBoard(db.Model):
    __tablename__ = 'analyse_board'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    analyse_id = db.Column(db.Integer, db.ForeignKey('analyse.analyse_id'), nullable=False)
    board_id = db.Column(db.String(255), nullable=False)
    board_name = db.Column(db.String(255), nullable=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation avec la table analyse
    analyse = db.relationship('Analyse', backref=db.backref('boards', lazy=True))

    def __init__(self, analyse_id, board_id, board_name, createdAt=None):
        self.analyse_id = analyse_id
        self.board_id = board_id
        self.board_name = board_name
        self.createdAt = createdAt or datetime.utcnow()

    def __repr__(self):
        return f'<AnalyseBoard {self.id}: {self.board_name}>'

    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'analyse_id': self.analyse_id,
            'board_id': self.board_id,
            'board_name': self.board_name,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None
        }

    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class Tickets(db.Model):
    __tablename__ = 'tickets'
    id_ticket = db.Column(db.Integer, primary_key=True, autoincrement=True)
    analyse_board_id = db.Column(db.Integer, db.ForeignKey('analyse_board.id'), nullable=False)
    ticket_metadata = db.Column(db.JSON, nullable=True)
    criticality_level = db.Column(db.Enum('low', 'medium', 'high', name='criticality_level_enum'), nullable=True)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation avec la table analyse_board
    analyse_board = db.relationship('AnalyseBoard', backref=db.backref('tickets', lazy=True))

    def __init__(self, analyse_board_id, ticket_metadata=None, criticality_level=None, createdAt=None):
        self.analyse_board_id = analyse_board_id
        self.ticket_metadata = ticket_metadata
        self.criticality_level = criticality_level
        self.createdAt = createdAt or datetime.utcnow()

    def __repr__(self):
        return f'<Tickets {self.id_ticket}: Board {self.analyse_board_id}>'

    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id_ticket': self.id_ticket,
            'analyse_board_id': self.analyse_board_id,
            'ticket_metadata': self.ticket_metadata,
            'criticality_level': self.criticality_level,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None
        }

    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
