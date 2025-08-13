from flask import Blueprint, jsonify, request
import logging
logger = logging.getLogger('agent_analyse')
import os
from datetime import datetime
from app.services.trello_service import get_trello_user_info
from app.services.criticality_analyzer import CriticalityAnalyzer
from app.models.trello_models import TrelloCard, CriticalityAnalysis, BoardAnalysisSummary, Config, Analyse, AnalyseBoard, Tickets, TicketAnalysisHistory
from app import db
from app.utils.crypto_service import crypto_service
from app.services.database_service import DatabaseService
from sqlalchemy import func
import requests
from tools.add_comment_tool import add_comment_to_card
import traceback
from tools.move_card_tool import move_card_to_list
import html
import re
from tools.add_etiquette_tool import apply_criticality_label_with_creation
from tools.add_etiquette_tool import apply_criticality_label_with_creation
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.response_builder import success, error
from app.services.reanalysis_service import ReanalysisService
from app.services.cache_service import CacheService
from app.services.statistics_service import StatisticsService
from app.services.config_service import ConfigService
from app.services.validators import require_json
trello_bp = Blueprint('trello', __name__)

# Note: Les routes de connexion Trello sont maintenant gérées côté frontend

@trello_bp.route('/api/trello/board/<board_id>/list/<list_id>/analyze', methods=['POST'])
def analyze_list_cards(board_id, list_id):
    """Analyse toutes les cartes d'une liste Trello et retourne la distribution.

    Body JSON:
        token (str, requis)
        board_name (str, optionnel)
        list_name (str, optionnel)
        analyse_board_id (int, optionnel)
    """
    try:
        data = request.get_json() or {}
        token = data.get('token')
        if not token:
            return error("Token Trello requis", status=400)
        board_name = data.get('board_name', 'Board sans nom')
        list_name = data.get('list_name', 'Liste sans nom')
        analyse_board_id = data.get('analyse_board_id')
        orchestrator = AnalysisOrchestrator(token)
        result = orchestrator.analyze_list(
            board_id=board_id,
            list_id=list_id,
            board_name=board_name,
            list_name=list_name,
            analyse_board_id=analyse_board_id
        )
        if 'error' in result:
            return error(result['error'], status=500)
        return success(result)
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error(f"Erreur lors de l'analyse: {str(e)}", status=500)


@trello_bp.route('/api/trello/card/<card_id>/add-label', methods=['POST'])
def add_label_to_card(card_id):
    """
    Add a criticality label to a specific Trello card.

    Body JSON attendu:
    {
        "board_id": "string",
        "token": "string",
        "criticality_level": "HIGH|MEDIUM|LOW"
    }
    """
    try:
        data = request.get_json() or {}
        ok, missing = require_json(data, ['board_id', 'token', 'criticality_level'])
        if not ok:
            return error(f"Champs requis manquants: {', '.join(missing)}", status=400)
        board_id = data['board_id']
        token = data['token']
        level = data['criticality_level'].upper()
        if level not in {'HIGH','MEDIUM','LOW'}:
            return error("criticality_level doit être HIGH, MEDIUM ou LOW", status=400)
        try:
            trello_resp = apply_criticality_label_with_creation(card_id=card_id, board_id=board_id, token=token, criticality_level=level)
        except Exception as e:  # noqa: BLE001
            return error(f"Erreur lors de l'ajout du label: {e}", status=500)
        return success({
            "message": f"Label de criticité '{level}' ajouté à la carte {card_id}",
            "card_id": card_id,
            "criticality_level": level,
            "trello_response": trello_resp
        })
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors du traitement: {str(e)}", status=500)


@trello_bp.route('/api/trello/card/<card_id>/add-comment', methods=['POST'])
def add_comment_to_card_endpoint(card_id):
    """
    Add a comment to a specific Trello card.

    Body JSON attendu:
    {
        "token": "string",
        "comment": "string"
    }
    """
    try:
        data = request.get_json() or {}
        ok, missing = require_json(data, ['token','comment'])
        if not ok:
            return error(f"Champs requis manquants: {', '.join(missing)}", status=400)
        try:
            trello_resp = add_comment_to_card(card_id=card_id, token=data['token'], comment=data['comment'])
        except Exception as e:  # noqa: BLE001
            return error(f"Erreur lors de l'ajout du commentaire: {e}", status=500)
        return success({
            "message": f"Commentaire ajouté à la carte {card_id}",
            "card_id": card_id,
            "comment": data['comment'],
            "trello_response": trello_resp
        })
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors du traitement: {e}", status=500)





@trello_bp.route('/api/trello/card/<card_id>/analyze', methods=['POST'])
def analyze_single_card_criticality(card_id):
    """
    Analyse la criticité d'une seule card Trello.

    Body JSON attendu:
    {
        "name": "string",
        "desc": "string",
        "due": "string|null",
        "list_name": "string",
        "board_id": "string",
        "board_name": "string",
        "labels": [...],
        "members": [...],
        "url": "string"
    }
    """
    try:
        payload = request.get_json() or {}
        ok, missing = require_json(payload, ['name','board_id'])
        if not ok:
            return error(f"Champs requis manquants: {', '.join(missing)}", status=400)
        payload['id'] = card_id
        analyzer = CriticalityAnalyzer()
        result = analyzer.analyze_card_criticality(payload)
        result['analyzed_at'] = datetime.utcnow().isoformat()
        return success(result)
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de l'analyse: {e}", status=500)



@trello_bp.route('/api/trello/config-board-subscription', methods=['POST'])
def config_board_subscription():
    """
    Capture les données Trello et les enregistre en base.
    Attend: token, board_id, board_name, list_id, list_name
    """
    try:
        raw = request.get_json() or {}
        # Normaliser pour accepter snake_case ou camelCase venant du front (target list optionnelle ici)
        normalized = {
            'token': raw.get('token'),
            'boardId': raw.get('board_id') or raw.get('boardId'),
            'boardName': raw.get('board_name') or raw.get('boardName'),
            'listId': raw.get('list_id') or raw.get('listId'),
            'listName': raw.get('list_name') or raw.get('listName'),
            'targetListId': raw.get('target_list_id') or raw.get('targetListId'),
            'targetListName': raw.get('target_list_name') or raw.get('targetListName'),
        }
        required_keys = ['token','boardId','boardName','listId','listName']
        missing = [k for k in required_keys if not normalized.get(k)]
        if missing:
            mapping = {
                'boardId': 'boardId (ou board_id)',
                'boardName': 'boardName (ou board_name)',
                'listId': 'listId (ou list_id)',
                'listName': 'listName (ou list_name)'
            }
            display = [mapping.get(m, m) for m in missing]
            return error(f"Champs manquants: {', '.join(display)}", status=400)
        db_service = DatabaseService()
        if not db_service.ensure_database_and_tables():
            return error("Erreur lors de la création de la base de données", status=500)
        cfg = Config(config_data=normalized)
        db.session.add(cfg)
        db.session.commit()
        return success({
            "message": "Configuration Trello enregistrée avec succès",
            "config_id": cfg.id,
            "config": normalized,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error(f"Erreur lors de la configuration: {e}", status=500)


@trello_bp.route('/api/trello/config-board-subscription', methods=['PUT'])
def update_board_subscription():
    """
    Met à jour une configuration d'abonnement aux boards Trello existante.
    Attend: id, et les champs à mettre à jour (ex: targetListId, targetListName)
    """
    try:
        raw = request.get_json() or {}
        if 'id' not in raw:
            return error("ID de configuration requis", status=400)
        # Normaliser les clés potentiellement envoyées en snake_case
        normalized_updates = {}
        mapping_pairs = [
            ('board_id','boardId'), ('board_name','boardName'),
            ('list_id','listId'), ('list_name','listName'),
            ('target_list_id','targetListId'), ('target_list_name','targetListName'),
            ('token','token')
        ]
        for snake, camel in mapping_pairs:
            if snake in raw and raw[snake] is not None:
                normalized_updates[camel] = raw[snake]
            if camel in raw and raw[camel] is not None:
                normalized_updates[camel] = raw[camel]
        cfg = ConfigService.update(raw['id'], normalized_updates)
        if not cfg:
            return error(f"Configuration {raw['id']} introuvable", status=404)
        return success({"message": "Configuration mise à jour avec succès", "config": cfg.to_dict()})
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error(f"Erreur lors de la mise à jour: {e}", status=500)


@trello_bp.route('/api/trello/config-board-subscription', methods=['GET'])
def get_board_subscriptions():
    """
    Récupère toutes les configurations d'abonnement aux boards Trello.
    """
    try:
        configs = [c.to_dict() for c in ConfigService.list_all()]
        return success({"total": len(configs), "configurations": configs})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la récupération: {e}", status=500)




@trello_bp.route('/api/trello/config-board-subscription/<board_id>/token', methods=['GET'])
def get_decrypted_token(board_id):
    """
    Récupère le token décrypté pour un board spécifique.
    ATTENTION: Route sensible - à protéger en production.
    """
    try:
        cfg = Config.query.filter(Config.config_data['boardId'].astext == board_id).first()
        if not cfg:
            return error(f"Configuration non trouvée pour le board {board_id}", status=404)
        try:
            decrypted = cfg.config_data.get('token')  # assuming already encrypted previously; adjust if needed
        except Exception as e:  # noqa: BLE001
            return error(f"Erreur lors du décryptage: {e}", status=500)
        return success({
            "board_id": board_id,
            "board_name": cfg.config_data.get('boardName'),
            "trello_token": decrypted
        })
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la récupération: {e}", status=500)


@trello_bp.route('/api/analyses', methods=['GET'])
def get_analyses():
    """
    API avec pagination, filtres et tri pour les analyses.

    Paramètres :
    - page (int) : Page actuelle (défaut: 1)
    - perPage (int) : Éléments par page (5|10|15, défaut: 10)
    - filters[] (list) : Filtres sous forme ["champ:opérateur:valeur"]
      Ex: ["createdAt:gte:2023-01-01", "tickets_count:gt:5"]
    - orderBy (str) : Champ de tri (createdAt, tickets_count, défaut: createdAt)
    - orderDirection (str) : asc ou desc (défaut: desc)
    """
    try:  # TODO move to dedicated service later
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('perPage', 5, type=int)
        filters = request.args.getlist('filters[]')
        order_by = request.args.get('orderBy', 'createdAt', type=str)
        order_direction = request.args.get('orderDirection', 'desc', type=str)

        per_page = per_page if per_page in {5, 10, 15} else 10
        order_by = order_by if order_by in {'createdAt', 'tickets_count'} else 'createdAt'
        order_direction = order_direction if order_direction in {'asc', 'desc'} else 'desc'

        # Base query - utiliser ticket_analysis_history pour compter les tickets par analyse
        query = db.session.query(
            Analyse,
            func.count(TicketAnalysisHistory.id).label('tickets_count')
        ).select_from(Analyse) \
         .outerjoin(TicketAnalysisHistory, TicketAnalysisHistory.analyse_id == Analyse.analyse_id) \
         .group_by(Analyse.analyse_id)

        applied_filters = []

        for f in filters:
            try:
                field, operator, value = f.split(':')

                if field == 'createdAt':
                    value = datetime.strptime(value, '%Y-%m-%d').date()

                    if operator == 'gte':
                        query = query.filter(Analyse.createdAt >= value)
                    elif operator == 'lte':
                        query = query.filter(Analyse.createdAt <= value)
                    elif operator == 'eq':
                        query = query.filter(func.date(Analyse.createdAt) == value)
                    elif operator == 'gt':
                        query = query.filter(Analyse.createdAt > value)
                    elif operator == 'lt':
                        query = query.filter(Analyse.createdAt < value)
                    else:
                        continue

                    applied_filters.append({"field": field, "operator": operator, "value": str(value)})

                elif field == 'tickets_count':
                    value = int(value)

                    if operator == 'gt':
                        query = query.having(func.count(TicketAnalysisHistory.id) > value)
                    elif operator == 'gte':
                        query = query.having(func.count(TicketAnalysisHistory.id) >= value)
                    elif operator == 'lt':
                        query = query.having(func.count(TicketAnalysisHistory.id) < value)
                    elif operator == 'lte':
                        query = query.having(func.count(TicketAnalysisHistory.id) <= value)
                    elif operator == 'eq':
                        query = query.having(func.count(TicketAnalysisHistory.id) == value)
                    else:
                        continue

                    applied_filters.append({"field": field, "operator": operator, "value": value})

            except Exception as filter_error:
                continue  # Ignore malformed filter

        # Sorting
        if order_by == 'tickets_count':
            sort_column = func.count(Tickets.id_ticket)
        else:
            sort_column = getattr(Analyse, order_by)

        query = query.order_by(
            sort_column.desc() if order_direction == 'desc' else sort_column.asc()
        )

        # Pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # Format results
        analyses_data = []
        for analysis, tickets_count in pagination.items:
            analysis_dict = {
                "analyse_id": analysis.analyse_id,
                "reference": analysis.reference,
                "createdAt": analysis.createdAt.isoformat() if analysis.createdAt else None,
                "updatedAt": analysis.updatedAt.isoformat() if analysis.updatedAt else None,
                "tickets_count": tickets_count
            }
            analyses_data.append(analysis_dict)

        pagination_payload = {
            "currentPage": pagination.page,
            "perPage": pagination.per_page,
            "totalPages": pagination.pages,
            "totalItems": pagination.total,
            "hasNext": pagination.has_next,
            "hasPrev": pagination.has_prev
        }
        # Backward compatibility: keep previous flattened keys and add meta.pagination
        return success({
            "data": analyses_data,
            "pagination": pagination_payload,  # (legacy access)
            "filters": applied_filters,
            "sort": {"orderBy": order_by, "orderDirection": order_direction}
        }, meta={
            "pagination": pagination_payload,
            "filters": applied_filters,
            "sort": {"orderBy": order_by, "orderDirection": order_direction}
        })

    except Exception as e:
        print("❌ Une erreur est survenue dans /api/analyses :")
        traceback.print_exc()
    return error(f"Erreur serveur: {e}", status=500)



@trello_bp.route('/api/tickets', methods=['GET'])
def get_tickets():
    """
    Liste paginée des tickets d'une analyse spécifique, avec filtres et tri.
    """
    try:  # keep logic until extracted
        analyse_id = request.args.get('analyse_id', type=int)
        if not analyse_id:
            return error("Paramètre analyse_id requis", status=400)

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('perPage', 10, type=int)
        filters = request.args.getlist('filters[]')
        order_by = request.args.get('orderBy', 'analyzed_at', type=str)
        order_direction = request.args.get('orderDirection', 'desc', type=str)

        per_page = per_page if per_page in {5, 10, 15} else 10
        order_by = order_by if order_by in {'criticality_level', 'analyzed_at', 'name'} else 'analyzed_at'
        order_direction = order_direction if order_direction in {'asc', 'desc'} else 'desc'

        # Import local nécessaire pour cette fonction
        from app.models.trello_models import TicketAnalysisHistory

        # Nouvelle logique : utiliser ticket_analysis_history pour trouver les tickets d'une analyse
        # sans duplication dans la table tickets
        query = db.session.query(Tickets).join(
            TicketAnalysisHistory, Tickets.id_ticket == TicketAnalysisHistory.ticket_id
        ).filter(TicketAnalysisHistory.analyse_id == analyse_id)

        applied_filters = []
        for f in filters:
            try:
                field, operator, value = f.split(':')
                if field == 'criticality_level' and operator == 'eq':
                    query = query.filter(Tickets.criticality_level == value.lower())
                    applied_filters.append({"field": field, "operator": operator, "value": value})
                elif field == 'name' and operator == 'contains':
                    query = query.filter(
                        func.json_unquote(func.json_extract(Tickets.ticket_metadata, '$.name')).ilike(f'%{value}%')
                    )
                    applied_filters.append({"field": field, "operator": operator, "value": value})
            except Exception:
                continue

        # Tri dynamique
        if order_by == 'criticality_level':
            sort_column = Tickets.criticality_level
        elif order_by == 'name':
            sort_column = func.json_unquote(func.json_extract(Tickets.ticket_metadata, '$.name'))
        elif order_by == 'analyzed_at':
            sort_column = func.json_unquote(func.json_extract(Tickets.ticket_metadata, '$.analysis_result.analyzed_at'))
        else:
            sort_column = Tickets.id_ticket

        query = query.order_by(sort_column.desc() if order_direction == 'desc' else sort_column.asc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        tickets_data = []
        for ticket in pagination.items:
            meta = ticket.ticket_metadata or {}
            # Récupérer la dernière analyse pour ce ticket avec info de réanalyse
            last_analysis = db.session.query(TicketAnalysisHistory).join(
                AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id
            ).join(
                Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id
            ).filter(
                TicketAnalysisHistory.ticket_id == ticket.id_ticket
            ).order_by(TicketAnalysisHistory.analyzed_at.desc()).first()

            if last_analysis:
                # Récupérer l'analyse associée pour le flag reanalyse
                analyse = db.session.query(Analyse).join(
                    AnalyseBoard, Analyse.analyse_id == AnalyseBoard.analyse_id
                ).filter(
                    AnalyseBoard.analyse_id == last_analysis.analyse_id
                ).first()

                justification = last_analysis.analyse_justification.get('justification') if last_analysis.analyse_justification else ''
                analyzed_at = last_analysis.analyzed_at.isoformat() if last_analysis.analyzed_at else None
                criticality_level = last_analysis.criticality_level.upper() if last_analysis.criticality_level else None
                is_reanalyse = analyse.reanalyse if analyse else False
            else:
                justification = ''
                analyzed_at = None
                criticality_level = None
                is_reanalyse = False

            tickets_data.append({
                "ticket_id": ticket.ticket_id,
                "id_ticket": ticket.id_ticket,
                "name": meta.get('name'),
                "desc": meta.get('desc'),
                "due": meta.get('due'),
                "url": meta.get('url'),
                "board_name": ticket.board_name,  # Ajouter le nom du board
                "criticality_level": criticality_level,
                "justification": justification,
                "analyzed_at": analyzed_at,
                "is_reanalyse": is_reanalyse  # Utiliser la variable calculée
            })

        pagination_payload = {
            "currentPage": pagination.page,
            "perPage": pagination.per_page,
            "totalPages": pagination.pages,
            "totalItems": pagination.total,
            "hasNext": pagination.has_next,
            "hasPrev": pagination.has_prev
        }
        return success({
            "data": tickets_data,
            "pagination": pagination_payload,
            "filters": applied_filters,
            "sort": {"orderBy": order_by, "orderDirection": order_direction}
        }, meta={
            "pagination": pagination_payload,
            "filters": applied_filters,
            "sort": {"orderBy": order_by, "orderDirection": order_direction}
        })

    except Exception as e:
        print("❌ Une erreur est survenue dans /api/tickets :")
        traceback.print_exc()
    return error(f"Erreur serveur: {e}", status=500)


@trello_bp.route('/api/analysis/cache/clear', methods=['POST'])
def clear_analysis_cache():
    """
    Supprime le cache d'analyse pour forcer une réanalyse de tous les tickets.

    Body JSON attendu (optionnel):
    {
        "ticket_id": "string" (optionnel - pour supprimer le cache d'un ticket spécifique)
    }
    """
    try:
        data = request.get_json() or {}
        ticket_id = data.get('ticket_id')
        if ticket_id:
            ok = CacheService.clear_ticket(ticket_id)
            if not ok:
                return error(f"Ticket {ticket_id} introuvable ou sans cache", status=404)
            return success({"message": f"Cache supprimé pour le ticket {ticket_id}", "cleared_tickets": 1})
        cleared = CacheService.clear_all()
        return success({"message": f"Cache supprimé pour {cleared} tickets", "cleared_tickets": cleared})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la suppression du cache: {e}", status=500)


@trello_bp.route('/api/analysis/cache/status', methods=['GET'])
def get_cache_status():
    """
    Récupère les statistiques du cache d'analyse.
    """
    try:
        return success({"cache_stats": CacheService.status()})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la récupération des statistiques: {e}", status=500)


@trello_bp.route('/api/tickets/<ticket_id>/analysis', methods=['GET'])
def get_ticket_analysis(ticket_id):
    """
    Récupère le résultat d'analyse en cache pour un ticket spécifique.
    """
    try:
        cached = Tickets.get_cached_analysis(ticket_id)
        if not cached:
            return error(f"Aucune analyse en cache pour le ticket {ticket_id}", status=404)
        return success({"ticket_id": ticket_id, "analysis_result": cached, "from_cache": True})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la récupération de l'analyse: {e}", status=500)

@trello_bp.route('/api/trello/card/<card_id>/move', methods=['PUT'])
def move_card(card_id):
    """
    Déplace une carte Trello vers une autre liste.

    Body JSON attendu :
    {
        "token": "string",
        "new_list_id": "string"
    }
    """
    try:
        data = request.get_json() or {}
        ok, missing = require_json(data, ['token','new_list_id'])
        if not ok:
            return error(f"Champs manquants: {', '.join(missing)}", status=400)
        try:
            result = move_card_to_list(card_id, data['new_list_id'], data['token'])
        except Exception as e:  # noqa: BLE001
            return error(f"Erreur déplacement: {e}", status=500)
        return success({"result": result, "card_id": card_id, "new_list_id": data['new_list_id']})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors du traitement: {e}", status=500)



@trello_bp.route('/api/tickets/<ticket_id>/reanalyze', methods=['POST'])
def reanalyze_ticket(ticket_id):
    """
    Réanalyse un ticket précis, enregistre le résultat dans ticket_analysis_history et retourne le nouveau résultat.
    """
    try:
        result = ReanalysisService.reanalyze(ticket_id)
        if 'error' in result:
            return error(result['error'], status=404 if 'introuvable' in result['error'] else 400)
        return success(result)
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la réanalyse: {e}", status=500)


@trello_bp.route('/api/tickets/<ticket_id>/analysis/history', methods=['GET'])
def get_ticket_analysis_history(ticket_id):
    """
    Retourne l'historique complet des analyses pour un ticket.
    """
    try:
        ticket = Tickets.get_by_ticket_id(ticket_id)
        if not ticket:
            return error(f"Ticket {ticket_id} introuvable", status=404)
        entries = db.session.query(TicketAnalysisHistory, Analyse).join(AnalyseBoard, TicketAnalysisHistory.analyse_id == AnalyseBoard.analyse_id).join(Analyse, AnalyseBoard.analyse_id == Analyse.analyse_id).filter(TicketAnalysisHistory.ticket_id == ticket.id_ticket).order_by(TicketAnalysisHistory.analyzed_at.desc()).all()
        history = [{
            "analysis_id": e.id,
            "analyse_id": e.analyse_id,
            "justification": e.analyse_justification.get('justification') if e.analyse_justification else '',
            "criticality_level": e.criticality_level,
            "analyzed_at": e.analyzed_at.isoformat() if e.analyzed_at else None,
            "reanalyse": a.reanalyse
        } for e, a in entries]
        return success({"ticket_id": ticket_id, "board_name": ticket.board_name, "history": history, "total": len(history)})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la récupération de l'historique: {e}", status=500)


@trello_bp.route('/api/analysis/statistics', methods=['GET'])
def get_analysis_statistics():
    """
    Retourne des statistiques sur les analyses et réanalyses.
    """
    try:
        stats = StatisticsService.global_stats()
        return success({"statistics": stats})
    except Exception as e:  # noqa: BLE001
        return error(f"Erreur lors de la récupération des statistiques: {e}", status=500)


@trello_bp.route('/api/trello/config-board-subscription/<int:config_id>/target-list', methods=['POST'])
def set_target_list(config_id):
    """
    Définit la liste cible pour le déplacement automatique des cartes après analyse.

    Body JSON attendu:
    {
        "targetListId": "string",
        "targetListName": "string"
    }
    """
    try:
        data = request.get_json() or {}
        target_list_id = data.get('targetListId') or data.get('target_list_id')
        target_list_name = data.get('targetListName') or data.get('target_list_name') or 'Liste cible'
        if not target_list_id:
            return error("targetListId (ou target_list_id) requis", status=400)
        cfg = ConfigService.set_target_list(config_id, target_list_id, target_list_name)
        if not cfg:
            return error(f"Configuration {config_id} introuvable", status=404)
        return success({
            "message": "Liste cible configurée avec succès",
            "config_id": config_id,
            "targetListId": target_list_id,
            "targetListName": target_list_name
        })
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        return error(f"Erreur lors de la configuration: {e}", status=500)

