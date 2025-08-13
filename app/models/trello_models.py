"""
Modèle de données pour les cards Trello et leur analyse de criticité.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from app import db
import json
from sqlalchemy.sql import func
from sqlalchemy import text
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
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, config_data, createdAt=None):
        self.config_data = config_data
        self.createdAt = createdAt or datetime.utcnow()
        self.updatedAt = datetime.utcnow()
    
    def __repr__(self):
        return f'<Config {self.id}>'
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'config_data': self.config_data,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
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
        
        return cls.query.filter(text("JSON_EXTRACT(config_data, '$.boardId') = :board_id")).params(board_id=board_id).first()


class Analyse(db.Model):
    __tablename__ = 'analyse'
    analyse_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reference = db.Column(db.String(64), unique=True, nullable=False)
    reanalyse = db.Column(db.Boolean, default=False)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, reference=None, reanalyse=False, createdAt=None):
        if reference is None:
            # Génère une référence unique basée sur la date et l'heure
            self.reference = f"analyse_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
        else:
            self.reference = reference
        self.reanalyse = reanalyse
        self.createdAt = createdAt or datetime.utcnow()
        self.updatedAt = datetime.utcnow()

    def __repr__(self):
        return f'<Analyse {self.analyse_id}: {self.reference}>'

    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'analyse_id': self.analyse_id,
            'reference': self.reference,
            'reanalyse': self.reanalyse,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
        }

    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def get_latest_analyses(cls, limit=10):
        """Récupère les dernières analyses créées."""
        from sqlalchemy import desc
        return cls.query.order_by(desc(cls.createdAt)).limit(limit).all()

    @classmethod
    def get_by_reference(cls, reference):
        """Récupère une analyse par sa référence."""
        return cls.query.filter_by(reference=reference).first()

    @classmethod
    def count_today(cls):
        """Compte le nombre d'analyses créées aujourd'hui."""
        from sqlalchemy import func
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return cls.query.filter(cls.createdAt >= today_start).count()


class AnalyseBoard(db.Model):
    __tablename__ = 'analyse_board'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    analyse_id = db.Column(db.Integer, db.ForeignKey('analyse.analyse_id'), nullable=False)
    platform = db.Column(db.String(60), nullable=True)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relation avec la table analyse
    analyse = db.relationship('Analyse', backref=db.backref('boards', lazy=True))

    def __init__(self, analyse_id, platform=None, createdAt=None):
        self.analyse_id = analyse_id
        self.platform = platform
        self.createdAt = createdAt or datetime.utcnow()
        self.updatedAt = datetime.utcnow()

    def __repr__(self):
        return f'<AnalyseBoard {self.id}>'

    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id': self.id,
            'analyse_id': self.analyse_id,
            'platform': self.platform,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
        }

    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def get_board_info_from_config(self, config_id=None):
        """
        Récupère les informations board_id, board_name, list_id, list_name
        depuis la table config pour cette analyse_board.
        
        Args:
            config_id (int, optional): ID de config spécifique. Si None, prend la dernière config.
        
        Returns:
            dict: Dictionnaire contenant board_id, board_name, list_id, list_name
        """
        if config_id:
            config = Config.query.get(config_id)
        else:
            config = Config.get_latest_config()
        
        if not config:
            return {
                'board_id': None,
                'board_name': None,
                'list_id': None,
                'list_name': None
            }
        
        config_data = config.config_data
        return {
            'board_id': config_data.get('boardId'),
            'board_name': config_data.get('boardName'),
            'list_id': config_data.get('listId'),
            'list_name': config_data.get('listName')
        }

    def get_board_id_from_config(self, config_id=None):
        """Récupère le board_id depuis la table config."""
        board_info = self.get_board_info_from_config(config_id)
        return board_info['board_id']

    def get_board_name_from_config(self, config_id=None):
        """Récupère le board_name depuis la table config."""
        board_info = self.get_board_info_from_config(config_id)
        return board_info['board_name']

    def get_list_id_from_config(self, config_id=None):
        """Récupère le list_id depuis la table config."""
        board_info = self.get_board_info_from_config(config_id)
        return board_info['list_id']

    def get_list_name_from_config(self, config_id=None):
        """Récupère le list_name depuis la table config."""
        board_info = self.get_board_info_from_config(config_id)
        return board_info['list_name']

    def to_dict_with_config_data(self, config_id=None):
        """
        Convertit l'objet en dictionnaire en incluant les données de config.
        """
        base_dict = self.to_dict()
        board_info = self.get_board_info_from_config(config_id)
        base_dict.update(board_info)
        return base_dict

class TicketAnalysisHistory(db.Model):
    __tablename__ = 'ticket_analysis_history'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id_ticket'), nullable=False)
    analyse_id = db.Column(db.Integer, db.ForeignKey('analyse.analyse_id'), nullable=False)
    analyse_justification = db.Column(db.JSON, nullable=True)
    criticality_level = db.Column(db.Enum('low', 'medium', 'high', name='criticality_level_enum'), nullable=True)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relations avec les tables tickets et analyse
    ticket = db.relationship('Tickets', backref=db.backref('analysis_history', lazy=True))
    analyse = db.relationship('Analyse', backref=db.backref('ticket_analysis_history', lazy=True))

    def __init__(self, ticket_id, analyse_id, analyse_justification=None, criticality_level=None, analyzed_at=None):
        self.ticket_id = ticket_id
        self.analyse_id = analyse_id
        self.analyse_justification = analyse_justification
        self.criticality_level = criticality_level
        self.analyzed_at = analyzed_at or datetime.utcnow()

    def __repr__(self):
        return f'<TicketAnalysisHistory {self.id}: Ticket {self.ticket_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'analyse_id': self.analyse_id,
            'analyse_justification': self.analyse_justification,
            'criticality_level': self.criticality_level,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None
        }

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

class Tickets(db.Model):
    __tablename__ = 'tickets'
    id_ticket = db.Column(db.Integer, primary_key=True, autoincrement=True)
    analyse_board_id = db.Column(db.Integer, db.ForeignKey('analyse_board.id'), nullable=False)
    ticket_id = db.Column(db.String(255), unique=True, nullable=True)
    ticket_metadata = db.Column(db.JSON, nullable=True)
    board_name = db.Column(db.String(255), nullable=True)
    createdAt = db.Column(db.DateTime, default=datetime.utcnow)
    updatedAt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
   
    # Relation avec la table analyse_board
    analyse_board = db.relationship('AnalyseBoard', backref=db.backref('tickets', lazy=True))

    def __init__(self, analyse_board_id, ticket_metadata=None, ticket_id=None, board_name=None, createdAt=None):
        self.analyse_board_id = analyse_board_id
        self.ticket_metadata = ticket_metadata
        self.ticket_id = ticket_id
        self.board_name = board_name
        self.createdAt = createdAt or datetime.utcnow()
        self.updatedAt = datetime.utcnow()

    def __repr__(self):
        return f'<Tickets {self.id_ticket}: Board {self.analyse_board_id}>'

    def to_dict(self):
        """Convertit l'objet en dictionnaire."""
        return {
            'id_ticket': self.id_ticket,
            'analyse_board_id': self.analyse_board_id,
            'ticket_id': self.ticket_id,
            'ticket_metadata': self.ticket_metadata,
            'board_name': self.board_name,
            'createdAt': self.createdAt.isoformat() if self.createdAt else None,
            'updatedAt': self.updatedAt.isoformat() if self.updatedAt else None
        }

    def to_json(self):
        """Convertit l'objet en JSON."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def get_by_ticket_id(cls, ticket_id):
        """Récupère un ticket par son ID externe (ex-Trello)."""
        return cls.query.filter_by(ticket_id=ticket_id).first()

    @classmethod
    def exists_by_ticket_id(cls, ticket_id):
        """Vérifie si un ticket avec cet ID externe existe déjà."""
        return cls.query.filter_by(ticket_id=ticket_id).first() is not None

    @classmethod
    def has_valid_analysis(cls, ticket_id):
        """Vérifie si un ticket a une analyse valide en cache."""
        ticket = cls.get_by_ticket_id(ticket_id)
        if not ticket or not ticket.ticket_metadata:
            return False
        return ticket.ticket_metadata.get('analysis_result') is not None

    @classmethod
    def get_cached_analysis(cls, ticket_id):
        """Récupère le résultat d'analyse en cache pour un ticket."""
        ticket = cls.get_by_ticket_id(ticket_id)
        if ticket and ticket.ticket_metadata:
            return ticket.ticket_metadata.get('analysis_result')
        return None

    @classmethod
    def invalidate_analysis_cache(cls, ticket_id):
        """Supprime le cache d'analyse pour forcer une réanalyse."""
        ticket = cls.get_by_ticket_id(ticket_id)
        if ticket and ticket.ticket_metadata:
            # Supprimer le résultat d'analyse du metadata
            metadata = ticket.ticket_metadata.copy()
            metadata.pop('analysis_result', None)
            ticket.ticket_metadata = metadata
            db.session.commit()
            return True
        return False

    @classmethod
    def clear_all_analysis_cache(cls):
        """Supprime tous les caches d'analyse pour forcer une réanalyse complète."""
        try:
            tickets = cls.query.all()
            for ticket in tickets:
                if ticket.ticket_metadata and 'analysis_result' in ticket.ticket_metadata:
                    metadata = ticket.ticket_metadata.copy()
                    metadata.pop('analysis_result', None)
                    ticket.ticket_metadata = metadata
            db.session.commit()
            return len(tickets)
        except Exception as e:
            db.session.rollback()
            raise e
