"""Service pour opérations sur Tickets et historique d'analyse."""
from __future__ import annotations
from typing import Any, Dict, Optional
from datetime import datetime
from app import db
from app.models.trello_models import Tickets, TicketAnalysisHistory


class TicketService:
    @staticmethod
    def get_by_external_id(ticket_id: str) -> Optional[Tickets]:
        return Tickets.get_by_ticket_id(ticket_id)

    @staticmethod
    def ensure_ticket(analyse_board_id: int, trello_card: Dict[str, Any], board_name: str, list_name: str) -> Tickets:
        existing = Tickets.get_by_ticket_id(trello_card['id'])
        if existing:
            return existing
        ticket = Tickets(
            analyse_board_id=analyse_board_id,
            ticket_id=trello_card['id'],
            board_name=board_name,
            ticket_metadata={
                'name': trello_card.get('name'),
                'desc': trello_card.get('desc', ''),
                'due': trello_card.get('due'),
                'url': trello_card.get('url'),
                'labels': trello_card.get('labels', []),
                'members': trello_card.get('members', []),
                'board_id': trello_card.get('board_id'),
                'board_name': board_name,
                'list_id': trello_card.get('list_id'),
                'list_name': list_name,
            }
        )
        db.session.add(ticket)
        db.session.flush()
        return ticket

    @staticmethod
    def save_history(ticket: Tickets, analyse_id: int, result: Dict[str, Any]):
        history = TicketAnalysisHistory(
            ticket_id=ticket.id_ticket,
            analyse_id=analyse_id,
            analyse_justification={'justification': result.get('justification')},
            criticality_level=result.get('criticality_level').lower() if result.get('criticality_level') else None,
            analyzed_at=datetime.utcnow()
        )
        db.session.add(history)
        return history

    @staticmethod
    def last_history(ticket: Tickets) -> Optional[TicketAnalysisHistory]:
        return TicketAnalysisHistory.query.filter_by(ticket_id=ticket.id_ticket).order_by(TicketAnalysisHistory.analyzed_at.desc()).first()

    @staticmethod
    def update_ticket_list(ticket: Tickets, new_list_id: str, new_list_name: Optional[str] = None) -> Tickets:
        """Met à jour la liste (id/nom) dans les métadonnées du ticket après déplacement et persiste."""
        try:
            meta = ticket.ticket_metadata or {}
            meta['list_id'] = new_list_id
            if new_list_name is not None:
                meta['list_name'] = new_list_name
            meta['last_moved_at'] = datetime.utcnow().isoformat()
            ticket.ticket_metadata = meta
            db.session.commit()
            return ticket
        except Exception:
            db.session.rollback()
            raise
