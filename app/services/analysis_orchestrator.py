"""Orchestrateur principal pour l'analyse de listes et cartes Trello."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from app import db
from app.services.trello_api_client import TrelloApiClient, TrelloApiError
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.services.ticket_service import TicketService
from app.models.trello_models import AnalyseBoard, Tickets, TicketAnalysisHistory, Config
import logging

logger = logging.getLogger('agent_analyse')


class AnalysisOrchestrator:
    def __init__(self, token: str):
        self.token = token
        self.trello_client = TrelloApiClient(token)
        self.analyzer = CriticalityAnalyzer()

    def analyze_list(self, board_id: str, list_id: str, board_name: str, list_name: str, analyse_board_id: Optional[int] = None) -> Dict[str, Any]:
        logger.debug(
            f"[ORCH] START analyze_list board_id={board_id} list_id={list_id} board_name='{board_name}' list_name='{list_name}' analyse_board_id={analyse_board_id}"
        )
        # Fetch cards
        try:
            cards = self.trello_client.get_list_cards(list_id)
        except TrelloApiError as e:
            logger.error(f"[ORCH] TrelloApiError get_list_cards: {e}")
            return {"error": str(e)}
        if not cards:
            logger.info(f"[ORCH] No cards returned for list {list_id}")
            return {
                "board_analysis": {
                    "board_id": board_id,
                    "board_name": board_name,
                    "list_id": list_id,
                    "list_name": list_name,
                    "total_cards": 0,
                    "analyzed_at": datetime.utcnow().isoformat(),
                },
                "cards_analysis": [],
            }
        # Prep structures
        analysis_results: List[Dict[str, Any]] = []
        saved_tickets: List[Dict[str, Any]] = []
        to_analyze: List[Dict[str, Any]] = []
        card_payload_map: Dict[str, Dict[str, Any]] = {}
        logger.debug(f"[ORCH] {len(cards)} card(s) fetched from Trello API")
        # Cache reuse or queue for analysis
        for card in cards:
            existing_ticket = Tickets.get_by_ticket_id(card['id'])
            if existing_ticket and existing_ticket.ticket_metadata:
                last_analysis = (
                    TicketAnalysisHistory.query
                    .filter_by(ticket_id=existing_ticket.id_ticket)
                    .order_by(TicketAnalysisHistory.analyzed_at.desc())
                    .first()
                )
                if last_analysis:
                    analysis_results.append({
                        'success': True,
                        'criticality_level': last_analysis.criticality_level.upper() if last_analysis.criticality_level else None,
                        'justification': last_analysis.analyse_justification.get('justification') if last_analysis.analyse_justification else None,
                        'analyzed_at': last_analysis.analyzed_at.isoformat() if last_analysis.analyzed_at else None,
                        'from_cache': True,
                        'card_id': card['id'],
                        'card_name': card['name']
                    })
                    if analyse_board_id:
                        saved_tickets.append({'ticket_id': card['id'], 'card_name': card['name'], 'from_cache': True})
                    continue
            payload = {
                'id': card['id'], 'name': card['name'], 'desc': card.get('desc', ''), 'due': card.get('due'),
                'list_name': list_name, 'board_id': board_id, 'board_name': board_name,
                'labels': card.get('labels', []), 'members': card.get('members', []), 'url': card.get('url')
            }
            card_payload_map[card['id']] = payload
            to_analyze.append(payload)
        # Batch analysis
        BATCH_SIZE = 8
        batched_results: Dict[str, Dict[str, Any]] = {}
        if to_analyze:
            logger.debug(f"[ORCH] Performing batch analysis on {len(to_analyze)} card(s) (batch_size={BATCH_SIZE})")
        for i in range(0, len(to_analyze), BATCH_SIZE):
            batch = to_analyze[i:i + BATCH_SIZE]
            logger.debug(f"[ORCH] Sending batch {i//BATCH_SIZE + 1}: {[c.get('id') for c in batch]}")
            batch_results = self.analyzer.analyze_cards_batch(batch)
            for r in batch_results:
                r['analyzed_at'] = datetime.utcnow().isoformat()
                batched_results[r['card_id']] = r
            logger.debug(f"[ORCH] Batch {i//BATCH_SIZE + 1} received results for {len(batch_results)} card(s)")
        # Actions & persistence
        for cid, payload in card_payload_map.items():
            result = batched_results.get(cid)
            if not result:
                logger.warning(f"[ORCH] Missing batch result for {cid}, fallback single analysis")
                result = self.analyzer.analyze_card_criticality(payload)
                result['analyzed_at'] = datetime.utcnow().isoformat()
            analysis_results.append(result)
            if result.get('success') and result.get('criticality_level') not in (None, 'OUT_OF_CONTEXT'):
                result['actions'] = {}
                # Label
                try:
                    self.trello_client.add_label(card_id=cid, board_id=board_id, criticality_level=result['criticality_level'])
                    result['actions']['label_added'] = True
                    logger.debug(f"[ORCH] Label applied to {cid} level={result['criticality_level']}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Label error card {cid}: {e}")
                    result['actions']['label_error'] = str(e)
                # Comment
                try:
                    if result.get('justification'):
                        self.trello_client.add_comment(card_id=cid, comment=result.get('justification'))
                        result['actions']['comment_added'] = True
                        logger.debug(f"[ORCH] Comment added to {cid}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Comment error card {cid}: {e}")
                    result['actions']['comment_error'] = str(e)
                # Move
                try:
                    config = Config.get_latest_config()
                    if config and config.config_data and config.config_data.get('targetListId'):
                        self.trello_client.move_card(card_id=cid, new_list_id=config.config_data['targetListId'])
                        result['card_moved'] = True
                        result['target_list_id'] = config.config_data['targetListId']
                        result['target_list_name'] = config.config_data.get('targetListName')
                        logger.debug(f"[ORCH] Card {cid} moved to {config.config_data['targetListId']}")
                    else:
                        logger.debug(f"[ORCH] No targetListId configured - skipping move for {cid}")
                except Exception as e:  # noqa: BLE001
                    result['card_moved'] = False
                    result['move_error'] = str(e)
                    logger.error(f"Move error card {cid}: {e}")
            # Persistence
            if analyse_board_id and result.get('success'):
                try:
                    ticket = TicketService.ensure_ticket(
                        analyse_board_id=analyse_board_id,
                        trello_card={**payload, 'list_id': list_id},
                        board_name=board_name,
                        list_name=list_name,
                    )
                    analyse_board = AnalyseBoard.query.get(analyse_board_id)
                    analyse_id = analyse_board.analyse_id if analyse_board else None
                    if analyse_id:
                        TicketService.save_history(ticket, analyse_id, result)
                        saved_tickets.append({'ticket_id': cid, 'card_name': payload['name']})
                        logger.debug(f"[ORCH] History saved ticket={ticket.id_ticket} analyse_id={analyse_id} card={cid}")
                    else:
                        logger.warning(f"[ORCH] analyse_id introuvable pour analyse_board_id={analyse_board_id}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Persistence error ticket {cid}: {e}")
        if saved_tickets:
            try:
                db.session.commit()
                logger.info(f"[ORCH] Commit success - {len(saved_tickets)} ticket history row(s) saved")
            except Exception as e:  # noqa: BLE001
                db.session.rollback()
                logger.error(f"Commit error: {e}")
                saved_tickets = []
        else:
            logger.debug("[ORCH] No tickets persisted (analyse_board_id absent ou aucun résultat nouveau)")
        # Summary
        total = len(analysis_results)
        successful = [r for r in analysis_results if r.get('success')]
        criticality_counts = {
            'CRITICAL_TOTAL': len(successful),
            'NON_CRITICAL': 0,
            'HIGH': len([r for r in successful if r.get('criticality_level') == 'HIGH']),
            'MEDIUM': len([r for r in successful if r.get('criticality_level') == 'MEDIUM']),
            'LOW': len([r for r in successful if r.get('criticality_level') == 'LOW']),
        }
        success_rate = (len(successful) / total * 100) if total else 0
        response = {
            'board_analysis': {
                'board_id': board_id,
                'board_name': board_name,
                'list_id': list_id,
                'list_name': list_name,
                'total_cards': total,
                'criticality_distribution': criticality_counts,
                'success_rate': round(success_rate, 2),
                'analyzed_at': datetime.utcnow().isoformat(),
            },
            'cards_analysis': analysis_results,
        }
        if saved_tickets:
            response['saved_tickets'] = saved_tickets
            response['tickets_saved_count'] = len(saved_tickets)
        logger.debug(f"[ORCH] END analyze_list total_cards={total} saved={len(saved_tickets)}")
        return response
