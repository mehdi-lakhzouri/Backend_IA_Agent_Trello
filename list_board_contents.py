#!/usr/bin/env python3
"""
Liste toutes les listes d'un board Trello avec le nombre de cartes.
"""

import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def list_board_contents():
    """Liste le contenu complet du board Trello."""
    
    # Configuration depuis votre log
    board_id = '67afaf01cf4a4ca4446f613c'
    token = 'ATTAaeba25c1a9c68845560cf32a0f5f4dc4cda56d5a4913c4f576ac51300d644a9b33918D95'
    
    trello_api_key = os.environ.get('TRELLO_API_KEY')
    
    print(f"📋 Analyse complète du board Trello")
    print(f"Board ID: {board_id}")
    print("=" * 60)
    
    if not trello_api_key or not token:
        print("❌ Configuration manquante")
        return
    
    try:
        # Récupérer toutes les listes du board
        lists_url = f"https://api.trello.com/1/boards/{board_id}/lists"
        lists_params = {
            'key': trello_api_key,
            'token': token,
            'fields': 'id,name,closed',
            'cards': 'open',  # Inclure les cartes ouvertes
            'card_fields': 'id,name'
        }
        
        response = requests.get(lists_url, params=lists_params)
        response.raise_for_status()
        lists_data = response.json()
        
        print(f"📝 Nombre de listes trouvées: {len(lists_data)}")
        print()
        
        for i, list_item in enumerate(lists_data, 1):
            list_name = list_item.get('name', 'Sans nom')
            list_id = list_item.get('id')
            is_closed = list_item.get('closed', False)
            cards = list_item.get('cards', [])
            cards_count = len(cards)
            
            status = "🔒 FERMÉE" if is_closed else "✅ OUVERTE"
            
            print(f"{i}. 📋 {list_name}")
            print(f"   ID: {list_id}")
            print(f"   Statut: {status}")
            print(f"   Cartes: {cards_count}")
            
            if cards_count > 0:
                print(f"   📋 Cartes dans cette liste:")
                for j, card in enumerate(cards, 1):
                    print(f"      {j}. {card.get('name', 'Sans nom')} (ID: {card.get('id')})")
            
            print("-" * 50)
        
        # Recommandations
        print("\n💡 RECOMMANDATIONS:")
        open_lists_with_cards = [l for l in lists_data if not l.get('closed', False) and len(l.get('cards', [])) > 0]
        
        if open_lists_with_cards:
            print("✅ Listes avec des cartes disponibles pour l'analyse:")
            for list_item in open_lists_with_cards:
                cards_count = len(list_item.get('cards', []))
                print(f"   • {list_item.get('name')} (ID: {list_item.get('id')}) - {cards_count} carte(s)")
        else:
            print("⚠️  Aucune liste ouverte ne contient de cartes.")
            print("   Pour tester l'analyse, vous pouvez:")
            print("   1. Ajouter des cartes à la liste 'À faire'")
            print("   2. Utiliser une autre liste qui contient des cartes")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la récupération des listes: {str(e)}")

if __name__ == "__main__":
    list_board_contents()
