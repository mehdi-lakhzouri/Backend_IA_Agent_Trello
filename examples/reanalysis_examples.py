"""
Exemple d'utilisation du service de réanalyse de tickets.
Ce fichier montre comment utiliser le service dans du code Python.
"""

from app.services.ticket_reanalysis_service import TicketReanalysisService
from app.models.trello_models import Config, Analyse, AnalyseBoard, Tickets
from app import create_app, db


def exemple_reanalyse_simple():
    """Exemple simple de réanalyse d'un ticket."""
    
    # Créer le contexte de l'application Flask
    app = create_app()
    
    with app.app_context():
        # Initialiser le service
        service = TicketReanalysisService()
        
        # ID du ticket à réanalyser (remplacez par un vrai ID)
        trello_ticket_id = "64f3a2b1c8e9d789"
        
        # Réanalyser le ticket avec la dernière configuration
        result = service.reanalyze_ticket(trello_ticket_id)
        
        if result['success']:
            print("✅ Réanalyse réussie!")
            print(f"Nouvelle analyse ID: {result['analysis']['analyse_id']}")
            print(f"Criticité: {result['ticket']['criticality_level']}")
        else:
            print(f"❌ Erreur: {result['error']}")


def exemple_reanalyse_avec_config():
    """Exemple de réanalyse avec une configuration spécifique."""
    
    app = create_app()
    
    with app.app_context():
        service = TicketReanalysisService()
        
        # Récupérer une configuration spécifique
        config = Config.query.first()
        if not config:
            print("❌ Aucune configuration trouvée")
            return
        
        trello_ticket_id = "64f3a2b1c8e9d789"
        
        # Réanalyser avec cette configuration
        result = service.reanalyze_ticket(trello_ticket_id, config.id)
        
        if result['success']:
            print("✅ Réanalyse avec configuration spécifique réussie!")
            print(f"Configuration utilisée: {result['config_used']['board_name']}")
        else:
            print(f"❌ Erreur: {result['error']}")


def exemple_historique_ticket():
    """Exemple de récupération de l'historique d'un ticket."""
    
    app = create_app()
    
    with app.app_context():
        service = TicketReanalysisService()
        
        trello_ticket_id = "64f3a2b1c8e9d789"
        
        # Récupérer l'historique
        result = service.get_ticket_reanalysis_history(trello_ticket_id)
        
        if result['success']:
            print(f"📚 Historique du ticket {trello_ticket_id}:")
            print(f"Total d'analyses: {result['total_analyses']}")
            
            for i, analysis in enumerate(result['history'][:3]):  # Afficher les 3 premières
                print(f"\n{i+1}. Analyse ID: {analysis['id_ticket']}")
                print(f"   Criticité: {analysis['criticality_level']}")
                print(f"   Date: {analysis['created_at']}")
                print(f"   Réanalyse: {'Oui' if analysis['is_reanalysis'] else 'Non'}")
        else:
            print(f"❌ Erreur: {result['error']}")


def exemple_reanalyse_lot():
    """Exemple de réanalyse de plusieurs tickets en lot."""
    
    app = create_app()
    
    with app.app_context():
        service = TicketReanalysisService()
        
        # Liste des tickets à réanalyser
        ticket_ids = [
            "64f3a2b1c8e9d789",
            "64f3a2b1c8e9d790",
            "64f3a2b1c8e9d791"
        ]
        
        results = []
        
        print("🔄 Réanalyse en lot...")
        for ticket_id in ticket_ids:
            print(f"  Traitement du ticket {ticket_id}...")
            
            result = service.reanalyze_ticket(ticket_id)
            results.append({
                'ticket_id': ticket_id,
                'success': result['success'],
                'criticality': result.get('ticket', {}).get('criticality_level') if result['success'] else None,
                'error': result.get('error') if not result['success'] else None
            })
        
        # Afficher les résultats
        print("\n📊 Résultats de la réanalyse en lot:")
        successful = 0
        for result in results:
            if result['success']:
                successful += 1
                print(f"✅ {result['ticket_id']}: {result['criticality']}")
            else:
                print(f"❌ {result['ticket_id']}: {result['error']}")
        
        print(f"\n🎯 {successful}/{len(results)} tickets réanalysés avec succès")


def exemple_comparaison_analyses():
    """Exemple de comparaison entre analyses d'un même ticket."""
    
    app = create_app()
    
    with app.app_context():
        service = TicketReanalysisService()
        
        trello_ticket_id = "64f3a2b1c8e9d789"
        
        # Récupérer l'historique
        history_result = service.get_ticket_reanalysis_history(trello_ticket_id)
        
        if not history_result['success'] or len(history_result['history']) < 2:
            print("❌ Pas assez d'analyses pour faire une comparaison")
            return
        
        analyses = history_result['history']
        latest = analyses[0]
        previous = analyses[1]
        
        print(f"🔍 Comparaison des analyses pour le ticket {trello_ticket_id}:")
        print(f"\n📊 Analyse la plus récente:")
        print(f"   Date: {latest['created_at']}")
        print(f"   Criticité: {latest['criticality_level']}")
        print(f"   Réanalyse: {'Oui' if latest['is_reanalysis'] else 'Non'}")
        
        print(f"\n📊 Analyse précédente:")
        print(f"   Date: {previous['created_at']}")
        print(f"   Criticité: {previous['criticality_level']}")
        print(f"   Réanalyse: {'Oui' if previous['is_reanalysis'] else 'Non'}")
        
        # Analyser l'évolution
        if latest['criticality_level'] != previous['criticality_level']:
            print(f"\n🔄 Évolution détectée:")
            print(f"   {previous['criticality_level']} → {latest['criticality_level']}")
            
            # Déterminer si c'est une amélioration ou dégradation
            criticality_order = {'low': 1, 'medium': 2, 'high': 3}
            latest_score = criticality_order.get(latest['criticality_level'], 0)
            previous_score = criticality_order.get(previous['criticality_level'], 0)
            
            if latest_score > previous_score:
                print("   📈 Dégradation de la criticité")
            elif latest_score < previous_score:
                print("   📉 Amélioration de la criticité")
        else:
            print(f"\n🟰 Aucun changement de criticité")


def exemple_gestion_erreurs():
    """Exemple de gestion des erreurs lors de la réanalyse."""
    
    app = create_app()
    
    with app.app_context():
        service = TicketReanalysisService()
        
        # Tenter de réanalyser un ticket inexistant
        fake_ticket_id = "ticket_inexistant_12345"
        
        print(f"🧪 Test avec un ticket inexistant: {fake_ticket_id}")
        result = service.reanalyze_ticket(fake_ticket_id)
        
        if not result['success']:
            error_code = result.get('error_code', 'UNKNOWN')
            print(f"❌ Erreur attendue: {error_code}")
            print(f"   Message: {result['error']}")
            
            # Gestion spécifique selon le type d'erreur
            if error_code == 'TRELLO_API_ERROR':
                print("💡 Suggestion: Vérifiez que le ticket existe sur Trello")
            elif error_code == 'NO_CONFIG':
                print("💡 Suggestion: Créez d'abord une configuration Trello")
            elif error_code == 'NO_TOKEN':
                print("💡 Suggestion: Vérifiez que le token Trello est configuré")
        else:
            print("🤔 Résultat inattendu - le ticket semble exister")


def main():
    """Fonction principale d'exemple."""
    print("🚀 Exemples d'utilisation du service de réanalyse")
    print("=" * 60)
    
    try:
        print("\n1. Réanalyse simple")
        print("-" * 30)
        exemple_reanalyse_simple()
        
        print("\n2. Réanalyse avec configuration spécifique")
        print("-" * 30)
        exemple_reanalyse_avec_config()
        
        print("\n3. Historique d'un ticket")
        print("-" * 30)
        exemple_historique_ticket()
        
        print("\n4. Réanalyse en lot")
        print("-" * 30)
        exemple_reanalyse_lot()
        
        print("\n5. Comparaison d'analyses")
        print("-" * 30)
        exemple_comparaison_analyses()
        
        print("\n6. Gestion des erreurs")
        print("-" * 30)
        exemple_gestion_erreurs()
        
    except Exception as e:
        print(f"❌ Erreur lors des exemples: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Exemples terminés!")


if __name__ == "__main__":
    main()
