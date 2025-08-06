# Changelog - Refactoring du système de réanalyse

## Vue d'ensemble des modifications

Ce document détaille les changements majeurs apportés au système d'analyse des tickets Trello, notamment le déplacement du champ `reanalyse` de la table `ticket_analysis_history` vers la table `analyse`.

## 🔄 Changements de schéma de base de données

### Migration `677466c3549a` - Déplacement du champ `reanalyse`

**Date**: Août 2025

**Objectif**: Améliorer la logique d'analyse en centralisant l'information de réanalyse au niveau de la session d'analyse plutôt qu'au niveau de chaque enregistrement d'historique.

#### Modifications apportées:
1. **Suppression** du champ `reanalyse` de la table `ticket_analysis_history`
2. **Ajout** du champ `reanalyse` dans la table `analyse`
3. **Mise à jour** de tous les modèles et routes associés

```sql
-- Migration appliquée
ALTER TABLE analyse ADD COLUMN reanalyse BOOLEAN DEFAULT FALSE;
ALTER TABLE ticket_analysis_history DROP COLUMN reanalyse;
```

## 📋 Fichiers modifiés

### 1. `agent_analyse.py`
**Modification**: Initialisation du champ `reanalyse=False` lors de la création d'une nouvelle session d'analyse.

```python
# Avant
analyse = Analyse(reference=reference, createdAt=datetime.now())

# Après  
analyse = Analyse(reference=reference, reanalyse=False, createdAt=datetime.now())
```

### 2. `app/models/trello_models.py`
**Modification**: Ajout du champ `reanalyse` au modèle `Analyse`.

```python
class Analyse(db.Model):
    # ... autres champs
    reanalyse = db.Column(db.Boolean, default=False)
```

### 3. `app/routes/trello.py`
**Modifications majeures**:

#### Route `/api/tickets/<ticket_id>/reanalyze`
- Création d'une nouvelle session d'analyse avec `reanalyse=True`
- Création d'un nouveau `AnalyseBoard` pour la réanalyse
- Enregistrement dans `ticket_analysis_history` lié à la nouvelle session

#### Route `/api/tickets`
- Utilisation de jointures pour récupérer le flag `reanalyse` depuis la table `analyse`
- Affichage du statut de réanalyse dans les réponses API

#### Route `/api/analysis/statistics`
- Mise à jour des requêtes pour compter les réanalyses via jointures
- Calcul correct des statistiques de réanalyse par board

#### Route `/api/tickets/<ticket_id>/analysis/history`
- Jointure avec la table `analyse` pour récupérer l'information de réanalyse
- Affichage de l'historique complet avec le statut de réanalyse

## 🔧 Logique métier

### Analyse initiale
- Champ `reanalyse=False` dans la table `analyse`
- Une seule session d'analyse pour tous les tickets d'un board
- Enregistrement dans `ticket_analysis_history` avec `analyse_id` de la session principale

### Réanalyse
- Création d'une **nouvelle session** d'analyse avec `reanalyse=True`
- Création d'un nouveau `AnalyseBoard` associé
- Enregistrement dans `ticket_analysis_history` avec le nouvel `analyse_id`
- Conservation de l'historique complet des analyses

## 📊 Impact sur les APIs

### Réponses modifiées

#### `/api/tickets` 
```json
{
  "data": [
    {
      "ticket_id": "card123",
      "name": "Ticket exemple",
      "criticality_level": "HIGH",
      "is_reanalyse": true,  // ← Nouveau champ
      "analyzed_at": "2025-08-05T10:30:00"
    }
  ]
}
```

#### `/api/analysis/statistics`
```json
{
  "statistics": {
    "total_analyses": 150,
    "initial_analyses": 120,
    "reanalyses": 30,           // ← Calcul mis à jour
    "reanalysis_rate": 20.0,    // ← Nouveau calcul
    "by_board": [
      {
        "board_name": "Project Board",
        "total_analyses": 50,
        "reanalyses": 10,        // ← Par board
        "initial_analyses": 40
      }
    ]
  }
}
```

#### `/api/tickets/<ticket_id>/analysis/history`
```json
{
  "history": [
    {
      "analysis_id": 123,
      "criticality_level": "HIGH",
      "reanalyse": true,         // ← Depuis table analyse
      "analyzed_at": "2025-08-05T10:30:00"
    }
  ]
}
```

## 🎯 Avantages du nouveau système

### 1. **Cohérence des données**
- Une session de réanalyse = un `analyse_id` unique
- Traçabilité claire entre analyses initiales et réanalyses

### 2. **Performance améliorée**
- Moins de redondance dans les données
- Requêtes optimisées avec jointures

### 3. **Logique métier clarifiée**
- Séparation nette entre sessions d'analyse et historique des tickets
- Facilite l'ajout de nouvelles fonctionnalités

### 4. **Évolutivité**
- Structure préparée pour de futures améliorations
- Possibilité d'analyser les patterns de réanalyse

## ⚠️ Points d'attention

### Migration des données
- ✅ Migration automatique appliquée
- ✅ Aucune perte de données
- ✅ Compatibilité ascendante maintenue

### Tests recommandés
1. **Vérifier les statistiques** après migration
2. **Tester la réanalyse** d'un ticket existant
3. **Valider l'affichage** des badges de réanalyse
4. **Contrôler l'historique** des tickets avec réanalyses

## 🚀 Prochaines étapes

### Côté Frontend
1. Adapter l'affichage du flag `is_reanalyse`
2. Mettre à jour les statistiques de réanalyse
3. Vérifier les badges d'indication de réanalyse

### Côté Backend
- ✅ Migration de base de données
- ✅ Mise à jour des modèles
- ✅ Modification des routes API
- ✅ Tests unitaires à jour

## 📝 Notes techniques

### Commandes de migration
```bash
# Migration appliquée
flask db upgrade

# Vérification
flask db current
# Résultat: 677466c3549a (head)
```

### Vérification de la migration
```sql
-- Vérifier la structure de la table analyse
DESCRIBE analyse;

-- Vérifier que reanalyse n'existe plus dans ticket_analysis_history  
DESCRIBE ticket_analysis_history;
```

## 👥 Équipes impactées

- **Backend**: ✅ Modifications terminées
- **Frontend**: 🔄 Adaptations requises
- **QA**: 🧪 Tests de régression recommandés

---

**Auteur**: GitHub Copilot  
**Date**: 5 août 2025  
**Version**: 1.0
