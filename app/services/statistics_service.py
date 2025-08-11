"""Service pour calculer les statistiques globales d'analyse."""
from __future__ import annotations
from app.models.trello_models import Tickets, TicketAnalysisHistory, AnalyseBoard, Analyse
from sqlalchemy import func
from app import db


class StatisticsService:
    @staticmethod
    def global_stats():
        total_analyses = TicketAnalysisHistory.query.count()
        total_tickets = Tickets.query.count()
        total_reanalyses = db.session.query(TicketAnalysisHistory).join(
            AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
        ).join(
            Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
        ).filter(Analyse.reanalyse.is_(True)).count()
        total_initial = total_analyses - total_reanalyses
        crit = {
            'high': TicketAnalysisHistory.query.filter_by(criticality_level='high').count(),
            'medium': TicketAnalysisHistory.query.filter_by(criticality_level='medium').count(),
            'low': TicketAnalysisHistory.query.filter_by(criticality_level='low').count(),
        }
        board_rows = db.session.query(
            Tickets.board_name, func.count(TicketAnalysisHistory.id).label('total')
        ).join(TicketAnalysisHistory, Tickets.id_ticket == TicketAnalysisHistory.ticket_id).group_by(Tickets.board_name).all()
        boards = []
        for board_name, total in board_rows:
            board_re = db.session.query(TicketAnalysisHistory).join(
                Tickets, TicketAnalysisHistory.ticket_id == Tickets.id_ticket
            ).join(
                AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
            ).join(
                Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
            ).filter(Tickets.board_name == board_name, Analyse.reanalyse.is_(True)).count()
            boards.append({
                'board_name': board_name,
                'total_analyses': total,
                'reanalyses': board_re,
                'initial_analyses': total - board_re
            })
        return {
            'total_tickets': total_tickets,
            'total_analyses': total_analyses,
            'initial_analyses': total_initial,
            'reanalyses': total_reanalyses,
            'reanalysis_rate': round((total_reanalyses / total_analyses * 100), 2) if total_analyses else 0,
            'criticality_distribution': crit,
            'by_board': boards,
        }
