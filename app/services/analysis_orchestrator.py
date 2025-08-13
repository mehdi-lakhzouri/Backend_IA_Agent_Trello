"""Orchestrateur principal pour l'analyse de listes et cartes Trello."""
from __future__ import annotations
import os
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
        
        
        card_index = 0
        while card_index < len(cards):
            card = cards[card_index]
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
                    card_index += 1
                    continue
            payload = {
                'id': card['id'], 'name': card['name'], 'desc': card.get('desc', ''), 'due': card.get('due'),
                'list_name': list_name, 'board_id': board_id, 'board_name': board_name,
                'labels': card.get('labels', []), 'members': card.get('members', []), 'url': card.get('url')
            }
            card_payload_map[card['id']] = payload
            to_analyze.append(payload)
            card_index += 1
        
        # Batch analysis - Remplacement de for par while
        BATCH_SIZE = int(os.getenv('ANALYSIS_BATCH_SIZE', '8'))
        batched_results: Dict[str, Dict[str, Any]] = {}
        if to_analyze:
            logger.debug(f"[ORCH] Performing batch analysis on {len(to_analyze)} card(s) (batch_size={BATCH_SIZE})")
        
        i = 0
        while i < len(to_analyze):
            batch = to_analyze[i:i + BATCH_SIZE]
            logger.debug(f"[ORCH] Sending batch {i//BATCH_SIZE + 1}: {[c.get('id') for c in batch]}")
            batch_results = self.analyzer.analyze_cards_batch(batch)
            
            result_index = 0
            while result_index < len(batch_results):
                r = batch_results[result_index]
                r['analyzed_at'] = datetime.utcnow().isoformat()
                batched_results[r['card_id']] = r
                result_index += 1
                
            logger.debug(f"[ORCH] Batch {i//BATCH_SIZE + 1} received results for {len(batch_results)} card(s)")
            i += BATCH_SIZE
        
        # Actions & persistence
        card_ids = list(card_payload_map.keys())
        cid_index = 0
        while cid_index < len(card_ids):
            cid = card_ids[cid_index]
            payload = card_payload_map[cid]
            result = batched_results.get(cid)
            if not result:
                logger.warning(f"[ORCH] Missing batch result for {cid}, fallback single analysis")
                result = self.analyzer.analyze_card_criticality(payload)
                result['analyzed_at'] = datetime.utcnow().isoformat()
            analysis_results.append(result)
            #todo check case no result returned
            if result.get('success') and result.get('criticality_level') not in (None, 'OUT_OF_CONTEXT'):
                result['actions'] = {}
                # Label
                self.trello_client.add_label(card_id=cid, board_id=board_id, criticality_level=result['criticality_level'])
                result['actions']['label_added'] = True
                logger.debug(f"[ORCH] Label applied to {cid} level={result['criticality_level']}")
                
                # Comment
                if result.get('justification'):
                    self.trello_client.add_comment(card_id=cid, comment=result.get('justification'))
                    result['actions']['comment_added'] = True
                    logger.debug(f"[ORCH] Comment added to {cid}")
                
                # Move
                config = Config.get_config_by_board(board_id)
                if config and config.config_data and config.config_data.get('targetListId'):
                    self.trello_client.move_card(card_id=cid, new_list_id=config.config_data['targetListId'])
                    result['card_moved'] = True
                    result['target_list_id'] = config.config_data['targetListId']
                    result['target_list_name'] = config.config_data.get('targetListName')
                    logger.debug(f"[ORCH] Card {cid} moved to {config.config_data['targetListId']}")
                else:
                    logger.debug(f"[ORCH] No targetListId configured - skipping move for {cid}")
            # Persistence
            if analyse_board_id and result.get('success'):
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
            cid_index += 1
            
        if saved_tickets:
            db.session.commit()
            logger.info(f"[ORCH] Commit success - {len(saved_tickets)} ticket history row(s) saved")
        else:
            logger.debug("[ORCH] No tickets persisted (analyse_board_id absent ou aucun résultat nouveau)")
        
        # Summary - Remplacement des list comprehensions qui utilisent for
        total = len(analysis_results)
        successful = []
        result_index = 0
        while result_index < len(analysis_results):
            r = analysis_results[result_index]
            if r.get('success'):
                successful.append(r)
            result_index += 1
        
        # Comptage des criticités
        high_count = 0
        medium_count = 0
        low_count = 0
        success_index = 0
        while success_index < len(successful):
            r = successful[success_index]
            if r.get('criticality_level') == 'HIGH':
                high_count += 1
            elif r.get('criticality_level') == 'MEDIUM':
                medium_count += 1
            elif r.get('criticality_level') == 'LOW':
                low_count += 1
            success_index += 1
        
        criticality_counts = {
            'CRITICAL_TOTAL': len(successful),
            'NON_CRITICAL': 0,
            'HIGH': high_count,
            'MEDIUM': medium_count,
            'LOW': low_count,
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