#!/usr/bin/env python3
"""
Agent d'analyse automatique des configurations Trello.

Ce script parcourt toutes les configurations dans la table 'config'
et crée une session d'analyse pour chacune dans la table 'analyse'.
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any
import requests

# Ajouter le répertoire racine au path pour les imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.trello_models import Config, Analyse, AnalyseBoard, Tickets


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
    
    return f"ANALYSE-{today}-{counter:03d}"


def extract_config_data(config: Config) -> Dict[str, Any]:
    """
    Extrait les données importantes de la configuration.
    """
    config_data = config.config_data
    
    return {
        'token': config_data.get('token'),
        'board_id': config_data.get('boardId'),
        'board_name': config_data.get('boardName'),
        'list_id': config_data.get('listId'),  # Ajouté
        'list_name': config_data.get('listName')  # Ajouté
    }


def create_global_analyse_session() -> Analyse:
    """
    Crée une session d'analyse globale pour toutes les configurations.
    """
    try:
        # Générer une référence unique
        reference = generate_unique_reference()
        
        # Créer la session d'analyse globale
        analyse = Analyse(
            reference=reference,
            createdAt=datetime.now()
        )
        
        # Sauvegarder en base
        db.session.add(analyse)
        db.session.commit()
        
        return analyse
        
    except Exception as e:
        db.session.rollback()
        raise e


def create_analyse_board(analyse: Analyse, config_data: Dict[str, Any]) -> AnalyseBoard:
    """
    Crée une entrée analyse_board pour un board spécifique.
    """
    try:
        analyse_board = AnalyseBoard(
            analyse_id=analyse.analyse_id,
            board_id=config_data['board_id'],
            board_name=config_data['board_name'],
            list_id=config_data.get('list_id'),  # Ajouté
            list_name=config_data.get('list_name'),  # Ajouté
            platform='trello',
            createdAt=datetime.now()
        )
        
        # Sauvegarder en base
        db.session.add(analyse_board)
        db.session.commit()
        
        return analyse_board
        
    except Exception as e:
        db.session.rollback()
        raise e


def check_flask_server_running() -> bool:
    """
    Vérifie si le serveur Flask est en cours d'exécution.
    """
    try:
        # Tester avec une API qui existe toujours
        response = requests.get("http://localhost:5000/api/trello/config-board-subscription", timeout=5)
        return response.status_code in [200, 404]  # 200 si configs existent, 404 sinon mais serveur UP
    except:
        return False


def analyze_board_list_via_api(analyse_board: AnalyseBoard, config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Utilise l'API interne pour analyser toutes les cartes d'une liste spécifique.
    """
    try:
        # Vérifier d'abord que le serveur est disponible
        if not check_flask_server_running():
            return {
                'success': False,
                'error': 'Serveur Flask non disponible - analyse des cartes ignorée'
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
        
        # Appel à l'API
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') == 'success':
            return {
                'success': True,
                'board_analysis': result.get('board_analysis', {}),
                'cards_count': result.get('board_analysis', {}).get('total_cards', 0),
                'tickets_saved': result.get('tickets_saved_count', 0),
                'criticality_distribution': result.get('board_analysis', {}).get('criticality_distribution', {})
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'Erreur inconnue lors de l\'analyse')
            }
            
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f'Erreur de requête API: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Erreur lors de l\'analyse: {str(e)}'
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
            print("❌ Aucune configuration trouvée dans la base de données.")
            return results
        
        print(f"🔍 {len(configs)} configuration(s) trouvée(s).")
        
        # Créer UNE SEULE session d'analyse pour toutes les configurations
        print("\n📝 Création d'une session d'analyse globale...")
        analyse = create_global_analyse_session()
        print(f"✅ Session d'analyse globale créée: {analyse.reference}")
        
        # Traiter chaque configuration et créer les analyse_board correspondantes
        valid_configs = []
        invalid_configs = []
        created_boards = []
        
        for config in configs:
            try:
                # Extraire les données de configuration
                config_data = extract_config_data(config)
                
                print(f"\n📋 Traitement de la configuration ID: {config.id}")
                print(f"   • Board: {config_data['board_name']} ({config_data['board_id']})")
                print(f"   • List: {config_data.get('list_name', 'N/A')} ({config_data.get('list_id', 'N/A')})")
                
                # Vérifier que les données essentielles sont présentes
                if not config_data['token'] or not config_data['board_id']:
                    print(f"   ⚠️  Configuration incomplète - Token ou Board ID manquant")
                    invalid_configs.append({
                        'config_id': config.id,
                        'status': 'error',
                        'message': 'Configuration incomplète - Token ou Board ID manquant',
                        'config_data': config_data
                    })
                    continue
                
                # Créer l'entrée analyse_board pour ce board
                analyse_board = create_analyse_board(analyse, config_data)
                print(f"   ✅ Analyse board créée: ID {analyse_board.id}")
                
                # Analyser les cartes de la liste si list_id est disponible
                analysis_result = None
                if config_data.get('list_id'):
                    print(f"   🔍 Analyse des cartes de la liste en cours...")
                    analysis_result = analyze_board_list_via_api(analyse_board, config_data)
                    
                    if analysis_result.get('success'):
                        cards_count = analysis_result.get('cards_count', 0)
                        tickets_saved = analysis_result.get('tickets_saved', 0)
                        criticality_dist = analysis_result.get('criticality_distribution', {})
                        
                        print(f"   ✅ Analyse terminée:")
                        print(f"      • Cartes analysées: {cards_count}")
                        print(f"      • Tickets sauvegardés: {tickets_saved}")
                        print(f"      • Criticité HIGH: {criticality_dist.get('HIGH', 0)}")
                        print(f"      • Criticité MEDIUM: {criticality_dist.get('MEDIUM', 0)}")
                        print(f"      • Criticité LOW: {criticality_dist.get('LOW', 0)}")
                    else:
                        print(f"   ⚠️  Erreur lors de l'analyse des cartes: {analysis_result.get('error', 'Erreur inconnue')}")
                else:
                    print(f"   ⚠️  Pas de list_id fourni - analyse des cartes ignorée")
                
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
                print(f"   ❌ Erreur lors du traitement de la configuration {config.id}: {str(e)}")
                invalid_configs.append({
                    'config_id': config.id,
                    'status': 'error',
                    'message': f'Erreur: {str(e)}',
                    'config_data': extract_config_data(config) if config else None
                })
        
        # Créer le résumé final avec l'analyse unique
        if valid_configs or invalid_configs:
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
        print(f"❌ Erreur générale lors du traitement des configurations: {str(e)}")
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
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DU TRAITEMENT")
    print("="*60)
    
    if not results:
        print("Aucun résultat à afficher.")
        return
    
    result = results[0]  # Il n'y a qu'un seul résultat maintenant
    
    if result['status'] == 'success':
        total_configs = result.get('total_configs', 0)
        valid_configs = result.get('valid_configs', [])
        invalid_configs = result.get('invalid_configs', [])
        
        print(f"Session d'analyse créée: {result['reference']}")
        print(f"Total des configurations analysées: {total_configs}")
        print(f"Configurations valides: {len(valid_configs)}")
        print(f"Configurations invalides: {len(invalid_configs)}")
        
        if invalid_configs:
            print("\n❌ CONFIGURATIONS INVALIDES:")
            for config_info in invalid_configs:
                board_name = config_info['config_data'].get('board_name', 'N/A')
                print(f"   • Config ID {config_info['config_id']} - {board_name}: {config_info['message']}")
        
        if valid_configs:
            print("\n✅ CONFIGURATIONS VALIDES:")
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
                    
                    print(f"   • Config ID {config_info['config_id']} - Board: {board_name}, List: {list_name}")
                    print(f"     📊 {cards_count} cartes analysées, {tickets_saved} tickets sauvegardés")
                    print(f"     🔥 HIGH: {criticality_dist.get('HIGH', 0)}, MEDIUM: {criticality_dist.get('MEDIUM', 0)}, LOW: {criticality_dist.get('LOW', 0)}")
                else:
                    print(f"   • Config ID {config_info['config_id']} - Board: {board_name}, List: {list_name}")
                    if config_info['config_data'].get('list_id'):
                        print(f"     ❌ Erreur lors de l'analyse des cartes")
                    else:
                        print(f"     ⚠️  Pas de list_id - analyse des cartes ignorée")
            
            if total_cards_analyzed > 0:
                print(f"\n📈 TOTAUX:")
                print(f"   • Total cartes analysées: {total_cards_analyzed}")
                print(f"   • Total tickets sauvegardés: {total_tickets_saved}")
    else:
        print(f"❌ Erreur générale: {result['message']}")
    
    print("\n💡 Une seule session d'analyse a été créée pour toutes les configurations.")


def main():
    """
    Fonction principale du script.
    """
    print("🚀 AGENT D'ANALYSE AUTOMATIQUE")
    print("="*50)
    print("Création d'une session d'analyse unique pour toutes les configurations...")
    
    # Vérifier que le serveur Flask est en cours d'exécution pour l'API
    print("\n🔍 Vérification du serveur Flask...")
    if not check_flask_server_running():
        print("⚠️  Le serveur Flask ne semble pas être en cours d'exécution.")
        print("   L'analyse des cartes sera ignorée. Pour activer l'analyse complète,")
        print("   démarrez le serveur Flask avec 'python run.py' dans un autre terminal.")
    else:
        print("✅ Serveur Flask détecté et opérationnel.")
    
    # Créer l'application Flask
    app = create_app()
    
    with app.app_context():
        try:
            # Traiter toutes les configurations et créer UNE session d'analyse
            results = process_all_configurations()
            
            # Afficher le résumé
            print_summary(results)
            
            print("\n🎉 Traitement terminé avec succès!")
            
        except Exception as e:
            print(f"\n💥 Erreur fatale: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()