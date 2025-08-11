"""Service de gestion du cache d'analyse (ticket_metadata.analysis_result)."""
from __future__ import annotations
from app.models.trello_models import Tickets


class CacheService:
    @staticmethod
    def clear_ticket(ticket_id: str) -> bool:
        return Tickets.invalidate_analysis_cache(ticket_id)

    @staticmethod
    def clear_all() -> int:
        return Tickets.clear_all_analysis_cache()

    @staticmethod
    def status():
        total = Tickets.query.count()
        cached = 0
        for t in Tickets.query.all():  # optimisation possible
            if t.ticket_metadata and t.ticket_metadata.get('analysis_result'):
                cached += 1
        uncached = total - cached
        ratio = (cached / total * 100) if total else 0
        return {
            'total_tickets': total,
            'cached_tickets': cached,
            'uncached_tickets': uncached,
            'cache_ratio_percent': round(ratio, 2)
        }
