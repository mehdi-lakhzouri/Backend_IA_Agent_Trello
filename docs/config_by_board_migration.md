# Migration vers Configuration par Board

## Vue d'ensemble

Le système a été modifié pour utiliser des configurations spécifiques par board au lieu d'une configuration globale "latest". Cette amélioration permet une gestion plus précise et flexible des règles de déplacement de cartes par board Trello.

## Changement principal

### Avant (Configuration globale)
```python
config = Config.get_latest_config()
```

### Après (Configuration par board)
```python
config = Config.get_config_by_board(board_id)
```

## Avantages de la nouvelle approche

### 1. **Précision par board**
- Chaque board Trello peut avoir sa propre configuration
- Déplacement des cartes vers la liste correcte selon le board analysé
- Évite les erreurs de déplacement vers des listes inappropriées

### 2. **Flexibilité multi-boards**
- Support de plusieurs boards avec des règles différentes
- Configuration indépendante par board
- Gestion personnalisée des workflows par équipe/projet

### 3. **Fiabilité**
- Élimination du risque d'utiliser une mauvaise configuration
- Correspondance exacte entre board analysé et configuration appliquée
- Comportement prévisible et cohérent

## Structure de la configuration

### Table Config
La table `config` stocke les configurations avec la structure JSON suivante :

```json
{
  "boardId": "board_123",
  "boardName": "Mon Board",
  "targetListId": "list_456", 
  "targetListName": "Done",
  "token": "trello_token"
}
```

### Méthode get_config_by_board
```python
@classmethod
def get_config_by_board(cls, board_id):
    """Récupère une configuration par board_id."""
    from sqlalchemy import text
    return cls.query.filter(
        text("JSON_EXTRACT(config_data, '$.boardId') = :board_id")
    ).params(board_id=board_id).first()
```

## Impact sur l'AnalysisOrchestrator

### Flux de traitement
1. **Analyse des cartes** du board spécifié
2. **Récupération de la configuration** pour ce board spécifique
3. **Application des actions** (label, commentaire, déplacement) selon cette configuration
4. **Déplacement vers la liste cible** définie pour ce board

### Code modifié
```python
# Dans analyze_list()
def analyze_list(self, board_id: str, list_id: str, ...):
    # ... analyse des cartes ...
    
    # Pour chaque carte analysée
    for card in analyzed_cards:
        if result.get('success'):
            # Récupération de la config spécifique au board
            config = Config.get_config_by_board(board_id)  # 🔄 CHANGEMENT ICI
            
            if config and config.config_data.get('targetListId'):
                # Déplacement vers la liste configurée pour ce board
                self.trello_client.move_card(
                    card_id=card_id, 
                    new_list_id=config.config_data['targetListId']
                )
```

## Cas d'usage

### Scenario 1: Boards multiples
```
Board Marketing (board_123)     → Liste "Marketing Done" (list_456)
Board Development (board_789)   → Liste "Dev Completed" (list_999) 
Board Sales (board_456)         → Liste "Sales Closed" (list_123)
```

### Scenario 2: Configuration par équipe
```
Équipe A: Cartes critiques → "À Réviser"
Équipe B: Cartes critiques → "Escalation"
Équipe C: Cartes critiques → "Actions Immédiates"
```

## Migration et tests

### Scripts de test disponibles
- `test_config_by_board.py` : Test de la méthode get_config_by_board
- `demo_config_approach.py` : Démonstration comparative des approches

### Commandes de test
```bash
# Test de base
python test_config_by_board.py

# Démonstration comparative
python demo_config_approach.py
```

## Compatibilité

### Rétrocompatibilité
- La méthode `get_latest_config()` reste disponible
- Aucune modification requise dans la structure de base de données
- Migration transparente pour les configurations existantes

### Fallback
Si aucune configuration n'est trouvée pour un board spécifique :
- Aucun déplacement de carte n'est effectué
- Les autres actions (labels, commentaires) continuent normalement
- Log informatif sur l'absence de configuration

## Bonnes pratiques

### Configuration recommandée
1. **Une configuration par board** analysé régulièrement
2. **Noms explicites** pour les listes cibles
3. **Validation** des IDs de listes avant configuration
4. **Documentation** des règles de déplacement par équipe

### Monitoring
- Surveiller les logs pour les boards sans configuration
- Vérifier la validité des `targetListId` configurés
- Contrôler la cohérence des déplacements effectués

Cette amélioration renforce la précision et la flexibilité du système d'analyse automatique des cartes Trello.
