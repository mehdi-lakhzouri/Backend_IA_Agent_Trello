
"""
Agent d'analyse automatique des configurations Trello.

Ce script parcourt toutes les configurations dans la table 'config'
et crée une session d'analyse pour chacune dans la table 'analyse'.
"""

import sys
import os
import logging
from datetime import datetime
from typing import List, Dict, Any
import requests
from logging.handlers import RotatingFileHandler
from tools.add_etiquette_tool import apply_criticality_label_with_creation
from tools.add_comment_tool import add_comment_to_card

# Ajouter le répertoire racine au path pour les imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.trello_models import Config, Analyse, AnalyseBoard, Tickets


def setup_logging() -> logging.Logger:
    """
    Configure le système de logging avec rotation des fichiers.
    """
    # Créer le répertoire logs s'il n'existe pas
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Nom du fichier de log basé sur la date
    log_filename = f"agent_analyse_{datetime.now().strftime('%Y%m%d')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)

    # Configuration du logger
    logger = logging.getLogger('agent_analyse')
    logger.setLevel(logging.DEBUG)

    # Éviter les doublons de handlers
    if logger.handlers:
        logger.handlers.clear()

    # Handler pour fichier avec rotation (max 10MB, 5 fichiers)
    file_handler = RotatingFileHandler(
        log_filepath,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # Handler pour console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Format des logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Initialiser le logger global
logger = setup_logging()


def generate_unique_reference() -> str:
    """
    Génère une référence unique pour l'analyse.
    Format: ANALYSE-YYYYMMDD-XXX
    """
    today = datetime.now().strftime('%Y%m%d')

    # Compter les analyses créées aujourd'hui
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_analyses = Analyse.query.filter(Analyse.createdAt >= today_start).count()

    # Incrémenter le compteur
    counter = today_analyses + 1

    reference = f"ANALYSE-{today}-{counter:03d}"
    logger.debug(f"Référence unique générée: {reference}")

    return reference


def extract_config_data(config: Config) -> Dict[str, Any]:
    """
    Extrait les données importantes de la configuration.
    """
    config_data = config.config_data

    extracted_data = {
        'token': config_data.get('token'),
        'board_id': config_data.get('boardId'),
        'board_name': config_data.get('boardName'),
        'list_id': config_data.get('listId'),  # Ajouté
        'list_name': config_data.get('listName')  # Ajouté
    }

    logger.debug(f"Extraction des données config ID {config.id}: {extracted_data.get('board_name', 'N/A')}")

    return extracted_data


def create_global_analyse_session() -> Analyse:
    """
    Crée une session d'analyse globale pour toutes les configurations.
    """
    try:
        # Générer une référence unique
        reference = generate_unique_reference()

        logger.info(f"Création d'une session d'analyse globale: {reference}")

        # Créer la session d'analyse globale
        analyse = Analyse(
            reference=reference,
            reanalyse=False,  # Mettre reanalyse à False lors de l'analyse initiale
            createdAt=datetime.now()
        )

        # Sauvegarder en base
        db.session.add(analyse)
        db.session.commit()

        logger.info(f"Session d'analyse créée avec succès: ID {analyse.analyse_id}")

        return analyse

    except Exception as e:
        logger.error(f"Erreur lors de la création de la session d'analyse: {str(e)}")
        db.session.rollback()
        raise e


def create_analyse_board(analyse: Analyse, config_data: Dict[str, Any]) -> AnalyseBoard:
    """
    Crée une entrée analyse_board pour un board spécifique.
    """
    try:
        logger.debug(f"Création analyse_board pour board: {config_data.get('board_name', 'N/A')}")

        analyse_board = AnalyseBoard(
            analyse_id=analyse.analyse_id,
            platform='trello',
            createdAt=datetime.now()
        )

        # Sauvegarder en base
        db.session.add(analyse_board)
        db.session.commit()

        logger.info(f"Analyse board créée: ID {analyse_board.id} pour analyse '{analyse.reference}'")

        return analyse_board

    except Exception as e:
        logger.error(f"Erreur lors de la création de l'analyse board: {str(e)}")
        db.session.rollback()
        raise e
        logger.error(f"Erreur lors de la création de l'analyse board: {str(e)}")
        db.session.rollback()
        raise e


def check_flask_server_running() -> bool:
    """
    Vérifie si le serveur Flask est en cours d'exécution.
    """
    try:
        logger.debug("Vérification de l'état du serveur Flask...")
        # Tester avec une API qui existe toujours
        response = requests.get("http://localhost:5000/api/trello/config-board-subscription", timeout=5)
        is_running = response.status_code in [200, 404]  # 200 si configs existent, 404 sinon mais serveur UP

        if is_running:
            logger.info("Serveur Flask détecté et opérationnel")
        else:
            logger.warning(f"Serveur Flask non disponible (statut: {response.status_code})")

        return is_running
    except requests.exceptions.RequestException as e:
        logger.warning(f"Serveur Flask non disponible: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du serveur Flask: {str(e)}")
        return False


def analyze_board_list_via_api(analyse_board: AnalyseBoard, config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Utilise l'API interne pour analyser toutes les cartes d'une liste spécifique.
    """
    try:
        board_name = config_data.get('board_name', 'N/A')
        list_name = config_data.get('list_name', 'N/A')

        logger.info(f"Début de l'analyse des cartes - Board: {board_name}, List: {list_name}")

        # Vérifier d'abord que le serveur est disponible
        if not check_flask_server_running():
            error_msg = 'Serveur Flask non disponible - analyse des cartes ignorée'
            logger.warning(error_msg)
            return {
                'success': False,
                'error': error_msg
            }

        # URL de l'API interne
        api_url = f"http://localhost:5000/api/trello/board/{config_data['board_id']}/list/{config_data['list_id']}/analyze"

        # Données à envoyer
        payload = {
            'token': config_data['token'],
            'board_name': config_data['board_name'],
            'list_name': config_data['list_name'],
            'analyse_board_id': analyse_board.id
        }

        logger.debug(f"Appel API: {api_url}")

        # Appel à l'API
        response = requests.post(api_url, json=payload, timeout=240)
        response.raise_for_status()

        result = response.json()

        if result.get('status') == 'success':
            cards_count = result.get('board_analysis', {}).get('total_cards', 0)
            tickets_saved = result.get('tickets_saved_count', 0)
            criticality_dist = result.get('board_analysis', {}).get('criticality_distribution', {})

            logger.info(f"Analyse terminée avec succès - {cards_count} cartes, {tickets_saved} tickets sauvegardés")
            logger.debug(f"Distribution criticité: {criticality_dist}")

            return {
                'success': True,
                'board_analysis': result.get('board_analysis', {}),
                'cards_count': cards_count,
                'tickets_saved': tickets_saved,
                'criticality_distribution': criticality_dist,
                'cards_analysis': result.get('cards_analysis', [])
            }
        else:
            error_msg = result.get('error', 'Erreur inconnue lors de l\'analyse')
            logger.error(f"Échec de l'analyse: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    except requests.exceptions.RequestException as e:
        error_msg = f'Erreur de requête API: {str(e)}'
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f'Erreur lors de l\'analyse: {str(e)}'
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


def process_all_configurations() -> List[Dict[str, Any]]:
    """
    Traite toutes les configurations et crée UNE SEULE session d'analyse globale.
    """
    results = []

    try:
        # Récupérer toutes les configurations
        configs = Config.query.all()

        if not configs:
            logger.warning("Aucune configuration trouvée dans la base de données")
            return results

        logger.info(f"{len(configs)} configuration(s) trouvée(s)")

        # Créer UNE SEULE session d'analyse pour toutes les configurations
        logger.info("Création d'une session d'analyse globale...")
        analyse = create_global_analyse_session()
        logger.info(f"Session d'analyse globale créée: {analyse.reference}")

        # Traiter chaque configuration et créer les analyse_board correspondantes
        valid_configs = []
        invalid_configs = []
        created_boards = []

        for config in configs:
            try:
                # Extraire les données de configuration
                config_data = extract_config_data(config)

                logger.info(f"Traitement de la configuration ID: {config.id}")
                logger.debug(f"Board: {config_data['board_name']} ({config_data['board_id']})")
                logger.debug(f"List: {config_data.get('list_name', 'N/A')} ({config_data.get('list_id', 'N/A')})")

                # Vérifier que les données essentielles sont présentes
                if not config_data['token'] or not config_data['board_id']:
                    error_msg = "Configuration incomplète - Token ou Board ID manquant"
                    logger.warning(f"Config ID {config.id}: {error_msg}")
                    invalid_configs.append({
                        'config_id': config.id,
                        'status': 'error',
                        'message': error_msg,
                        'config_data': config_data
                    })
                    continue

                # Créer l'entrée analyse_board pour ce board
                analyse_board = create_analyse_board(analyse, config_data)

                # Analyser les cartes de la liste si list_id est disponible
                analysis_result = None
                if config_data.get('list_id'):
                    logger.info("Analyse des cartes de la liste en cours...")
                    analysis_result = analyze_board_list_via_api(analyse_board, config_data)

                    if analysis_result.get('success'):
                        cards_count = analysis_result.get('cards_count', 0)
                        tickets_saved = analysis_result.get('tickets_saved', 0)
                        criticality_dist = analysis_result.get('criticality_distribution', {})

                        logger.info(f"Analyse terminée - Cartes: {cards_count}, Tickets: {tickets_saved}")
                        logger.debug(f"Criticité HIGH: {criticality_dist.get('HIGH', 0)}, "
                                   f"MEDIUM: {criticality_dist.get('MEDIUM', 0)}, "
                                   f"LOW: {criticality_dist.get('LOW', 0)}")
                        # Plus d'appel local des tools : tout est géré côté API Flask
                        logger.debug("Traitement des cartes (labels/commentaires) délégué à l'API Flask.")
                    else:
                        logger.error(f"Erreur lors de l'analyse des cartes: {analysis_result.get('error', 'Erreur inconnue')}")
                else:
                    logger.info("Pas de list_id fourni - analyse des cartes ignorée")

                valid_configs.append({
                    'config_id': config.id,
                    'analyse_board_id': analyse_board.id,
                    'status': 'success',
                    'message': 'Configuration traitée avec succès',
                    'config_data': config_data,
                    'analysis_result': analysis_result
                })

                created_boards.append(analyse_board)

            except Exception as e:
                error_msg = f"Erreur lors du traitement de la configuration {config.id}: {str(e)}"
                logger.error(error_msg)
                invalid_configs.append({
                    'config_id': config.id,
                    'status': 'error',
                    'message': f'Erreur: {str(e)}',
                    'config_data': extract_config_data(config) if config else None
                })

        # Créer le résumé final avec l'analyse unique
        if valid_configs or invalid_configs:
            logger.info(f"Traitement terminé - {len(valid_configs)} valides, {len(invalid_configs)} invalides")
            results.append({
                'analyse_id': analyse.analyse_id,
                'reference': analyse.reference,
                'status': 'success',
                'message': f'Session d\'analyse créée pour {len(configs)} configuration(s)',
                'valid_configs': valid_configs,
                'invalid_configs': invalid_configs,
                'created_boards': created_boards,
                'total_configs': len(configs)
            })

    except Exception as e:
        error_msg = f"Erreur générale lors du traitement des configurations: {str(e)}"
        logger.error(error_msg)
        results.append({
            'status': 'error',
            'message': f'Erreur générale: {str(e)}',
            'valid_configs': [],
            'invalid_configs': [],
            'created_boards': [],
            'total_configs': 0
        })

    return results


def print_summary(results: List[Dict[str, Any]]) -> None:
    """
    Affiche un résumé du traitement effectué.
    """
    logger.info("=" * 60)
    logger.info("RÉSUMÉ DU TRAITEMENT")
    logger.info("=" * 60)

    if not results:
        logger.warning("Aucun résultat à afficher")
        return

    result = results[0]  # Il n'y a qu'un seul résultat maintenant

    if result['status'] == 'success':
        total_configs = result.get('total_configs', 0)
        valid_configs = result.get('valid_configs', [])
        invalid_configs = result.get('invalid_configs', [])

        logger.info(f"Session d'analyse créée: {result['reference']}")
        logger.info(f"Total des configurations analysées: {total_configs}")
        logger.info(f"Configurations valides: {len(valid_configs)}")
        logger.info(f"Configurations invalides: {len(invalid_configs)}")

        if invalid_configs:
            logger.warning("CONFIGURATIONS INVALIDES:")
            for config_info in invalid_configs:
                board_name = config_info['config_data'].get('board_name', 'N/A')
                logger.warning(f"Config ID {config_info['config_id']} - {board_name}: {config_info['message']}")

        if valid_configs:
            logger.info("CONFIGURATIONS VALIDES:")
            total_cards_analyzed = 0
            total_tickets_saved = 0

            for config_info in valid_configs:
                board_name = config_info['config_data'].get('board_name', 'N/A')
                list_name = config_info['config_data'].get('list_name', 'N/A')
                analysis_result = config_info.get('analysis_result')

                if analysis_result and analysis_result.get('success'):
                    cards_count = analysis_result.get('cards_count', 0)
                    tickets_saved = analysis_result.get('tickets_saved', 0)
                    criticality_dist = analysis_result.get('criticality_distribution', {})

                    total_cards_analyzed += cards_count
                    total_tickets_saved += tickets_saved

                    logger.info(f"Config ID {config_info['config_id']} - Board: {board_name}, List: {list_name}")
                    logger.info(f"  {cards_count} cartes analysées, {tickets_saved} tickets sauvegardés")
                    logger.info(f"  HIGH: {criticality_dist.get('HIGH', 0)}, MEDIUM: {criticality_dist.get('MEDIUM', 0)}, LOW: {criticality_dist.get('LOW', 0)}")
                else:
                    logger.info(f"Config ID {config_info['config_id']} - Board: {board_name}, List: {list_name}")
                    if config_info['config_data'].get('list_id'):
                        logger.warning(f"  Erreur lors de l'analyse des cartes: {analysis_result.get('error', 'Erreur inconnue')}")
                    else:
                        logger.info("  Pas de list_id - analyse des cartes ignorée")

            if total_cards_analyzed > 0:
                logger.info("TOTAUX:")
                logger.info(f"  Total cartes analysées: {total_cards_analyzed}")
                logger.info(f"  Total tickets sauvegardés: {total_tickets_saved}")
    else:
        logger.error(f"Erreur générale: {result['message']}")

    logger.info("Une seule session d'analyse a été créée pour toutes les configurations")


def main():
    """
    Fonction principale du script.
    """
    logger.info("AGENT D'ANALYSE AUTOMATIQUE")
    logger.info("=" * 50)
    logger.info("Création d'une session d'analyse unique pour toutes les configurations...")

    # Vérifier que le serveur Flask est en cours d'exécution pour l'API
    logger.info("Vérification du serveur Flask...")
    if not check_flask_server_running():
        logger.warning("Le serveur Flask ne semble pas être en cours d'exécution")
        logger.warning("L'analyse des cartes sera ignorée. Pour activer l'analyse complète,")
        logger.warning("démarrez le serveur Flask avec 'python run.py' dans un autre terminal")
    else:
        logger.info("Serveur Flask détecté et opérationnel")

    # Créer l'application Flask
    app = create_app()

    with app.app_context():
        try:
            # Traiter toutes les configurations et créer UNE session d'analyse
            results = process_all_configurations()

            # Afficher le résumé
            print_summary(results)

            logger.info("Traitement terminé avec succès!")

        except Exception as e:
            logger.error(f"Erreur fatale: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
