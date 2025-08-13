# Configuration de la Taille de Batch pour l'Analyse

## Vue d'ensemble

La taille du batch pour l'analyse des cartes Trello est maintenant configurable via les variables d'environnement au lieu d'être codée en dur dans le code.

## Configuration

### Variable d'environnement

Ajoutez la variable suivante à votre fichier `.env` :

```env
# Configuration Analyse
ANALYSIS_BATCH_SIZE=8
```

### Valeurs recommandées

- **Petites charges (1-20 cartes)** : `ANALYSIS_BATCH_SIZE=4`
- **Charges moyennes (20-100 cartes)** : `ANALYSIS_BATCH_SIZE=8` (valeur par défaut)
- **Grandes charges (100+ cartes)** : `ANALYSIS_BATCH_SIZE=12` ou `ANALYSIS_BATCH_SIZE=16`

### Considérations de performance

- **Batch trop petit** : Plus de requêtes API, potentiellement plus lent
- **Batch trop grand** : Risque de timeout, consommation mémoire plus élevée
- **Batch optimal** : Équilibre entre performance et fiabilité

## Utilisation

### Dans le code

```python
# L'AnalysisOrchestrator charge automatiquement la valeur depuis .env
BATCH_SIZE = int(os.getenv('ANALYSIS_BATCH_SIZE', '8'))
```

### Valeur par défaut

Si la variable `ANALYSIS_BATCH_SIZE` n'est pas définie, la valeur par défaut est **8**.

## Tests

Deux scripts de test sont disponibles pour vérifier la configuration :

1. **Test de base** :
   ```bash
   python test_batch_config.py
   ```

2. **Test d'intégration** :
   ```bash
   python test_orchestrator_batch.py
   ```

## Migration

### Avant (codé en dur)
```python
BATCH_SIZE = 8  # Valeur fixe
```

### Après (configurable)
```python
BATCH_SIZE = int(os.getenv('ANALYSIS_BATCH_SIZE', '8'))  # Configurable via .env
```

## Avantages

1. **Flexibilité** : Ajustement de la performance sans modification du code
2. **Environnements différents** : Configuration spécifique par environnement (dev, staging, prod)
3. **Optimisation** : Possibilité d'ajuster selon les ressources disponibles
4. **Maintenance** : Moins de changements de code nécessaires

## Dépannage

### Variable non reconnue

Vérifiez que :
1. Le fichier `.env` contient `ANALYSIS_BATCH_SIZE=<valeur>`
2. La variable est bien chargée avec `load_dotenv()`
3. La valeur est un nombre entier valide

### Performance dégradée

- Réduisez la taille du batch si vous observez des timeouts
- Augmentez la taille du batch si les performances sont lentes avec de nombreuses petites requêtes
