"""Service dédié à la réanalyse d'un ticket existant."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any
from app import db
from app.models.trello_models import Tickets, TicketAnalysisHistory, AnalyseBoard, Analyse
from app.services.criticality_analyzer import CriticalityAnalyzer


class ReanalysisService:
    @staticmethod
    def reanalyze(ticket_id: str) -> Dict[str, Any]:
        ticket = Tickets.get_by_ticket_id(ticket_id)
        if not ticket:
            return {"error": f"Ticket {ticket_id} introuvable"}
        meta = ticket.ticket_metadata or {}
        card_data = {
            'id': ticket.ticket_id,
            'name': meta.get('name'),
            'desc': meta.get('desc', ''),
            'due': meta.get('due'),
            'list_name': meta.get('list_name'),
            'board_id': meta.get('board_id'),
            'board_name': meta.get('board_name'),
            'labels': meta.get('labels', []),
            'members': meta.get('members', []),
            'url': meta.get('url'),
        }
        previous_record = TicketAnalysisHistory.query.filter_by(ticket_id=ticket.id_ticket).order_by(TicketAnalysisHistory.analyzed_at.desc()).first()
        prev = {}
        if previous_record:
            prev = {
                'criticality_level': previous_record.criticality_level,
                'justification': previous_record.analyse_justification.get('justification', '') if previous_record.analyse_justification else '',
                'analyzed_at': previous_record.analyzed_at.isoformat() if previous_record.analyzed_at else None,
            }
        analyzer = CriticalityAnalyzer()
        result = analyzer.reanalyze_card_criticality(card_data, prev)
        result['analyzed_at'] = datetime.utcnow().isoformat()
        reanalyse_session = Analyse(reference=f"REANALYSE-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}", reanalyse=True, createdAt=datetime.utcnow())
        db.session.add(reanalyse_session)
        db.session.flush()
        analyse_board = AnalyseBoard(analyse_id=reanalyse_session.analyse_id, platform='trello', createdAt=datetime.utcnow())
        db.session.add(analyse_board)
        db.session.flush()
        history = TicketAnalysisHistory(ticket_id=ticket.id_ticket, analyse_id=reanalyse_session.analyse_id, analyse_justification={'justification': result.get('justification')}, criticality_level=result.get('criticality_level'), analyzed_at=datetime.utcnow())
        db.session.add(history)
        if ticket.ticket_metadata:
            ticket.ticket_metadata['analysis_result'] = result
        else:
            ticket.ticket_metadata = {'analysis_result': result}
        db.session.commit()
        return {
            'ticket_id': ticket_id,
            'analysis_result': result,
            'reanalysis_info': {
                'is_reanalysis': True,
                'session_reference': reanalyse_session.reference,
                'analysis_session_id': reanalyse_session.analyse_id,
                'previous_analysis': prev or None,
                'enhanced_verification': True,
            }
        }
