"""Gestion des sessions d'analyse (Analyse + AnalyseBoard)."""
from __future__ import annotations
from datetime import datetime
from app import db
from app.models.trello_models import Analyse, AnalyseBoard


class AnalyseSessionService:
    @staticmethod
    def create_session(reanalyse: bool = False) -> Analyse:
        analyse = Analyse(reanalyse=reanalyse, createdAt=datetime.utcnow())
        db.session.add(analyse)
        db.session.flush()
        return analyse

    @staticmethod
    def link_board(analyse_id: int, platform: str = 'trello') -> AnalyseBoard:
        board = AnalyseBoard(analyse_id=analyse_id, platform=platform, createdAt=datetime.utcnow())
        db.session.add(board)
        db.session.flush()
        return board
