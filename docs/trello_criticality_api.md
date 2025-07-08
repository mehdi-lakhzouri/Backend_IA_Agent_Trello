# APIs d'Analyse de Criticité des Cards Trello v2

## Vue d'ensemble

Ce module fournit des APIs pour analyser la criticité des cards Trello en utilisant l'intelligence artificielle Gemini 1.5 Flash. 

### 🎯 **Nouvelles fonctionnalités v2 :**
- **Format OUI/NON** : L'IA répond d'abord si la card est critique ou non
- **Contexte documenté** : Se base sur les documents uploadés via l'API upload
- **Historique intelligent** : Utilise les cards précédemment analysées pour maintenir la cohérence
- **Sauvegarde automatique** : Chaque analyse est sauvegardée dans ChromaDB

## Fonctionnement

### 📚 **Sources d'analyse :**
1. **Documents uploadés** : Description de votre application stockée dans ChromaDB
2. **Historique des cards** : Cards similaires précédemment analysées
3. **Données de la card** : Titre, description, labels, échéances, etc.

### 🤖 **Processus d'analyse :**
1. L'IA récupère le contexte de l'application depuis vos documents
2. Elle trouve des cards similaires dans l'historique
3. Elle analyse la nouvelle card avec ce contexte enrichi
4. Elle répond par **OUI** (critique) ou **NON** (pas critique)
5. Si critique, elle précise le niveau : **HIGH**, **MEDIUM**, **LOW**

## Format de réponse

### **Ancienne réponse :**
```json
{
  "criticality_level": "HIGH"
}
```

### **Nouvelle réponse v2 :**
```json
{
  "card_id": "507f191e810c19729de860ea",
  "card_name": "Correction bug critique login", 
  "is_critical": true,
  "criticality_level": "HIGH",
  "raw_response": "OUI HIGH",
  "analyzed_at": "2025-07-03T15:30:00Z",
  "success": true
}
```

## Statistiques mises à jour

Les statistiques incluent maintenant la répartition critique/non-critique :

```json
{
  "criticality_distribution": {
    "CRITICAL_TOTAL": 5,
    "NON_CRITICAL": 3,
    "HIGH": 2,
    "MEDIUM": 2, 
    "LOW": 1
  }
}
```

## Endpoints disponibles

### 1. Analyse de criticité pour un board complet

**POST** `/api/trello/cards/analyze`

Analyse toutes les cards d'un board Trello.

**Body JSON:**
```json
{
    "board_id": "507f1f77bcf86cd799439011",
    "board_name": "Projet Principal",
    "cards": [
        {
            "id": "507f191e810c19729de860ea",
            "name": "Correction bug critique login",
            "desc": "Les utilisateurs ne peuvent pas se connecter depuis ce matin",
            "due": "2025-07-04T10:00:00Z",
            "list_name": "En cours",
            "labels": [
                {"name": "Bug", "color": "red"},
                {"name": "Urgent", "color": "orange"}
            ],
            "members": [
                {"fullName": "John Doe"}
            ],
            "url": "https://trello.com/c/..."
        }
    ]
}
```

**Réponse:**
```json
{
    "board_analysis": {
        "board_id": "507f1f77bcf86cd799439011",
        "board_name": "Projet Principal",
        "total_cards": 1,
        "criticality_distribution": {
            "HIGH": 1,
            "MEDIUM": 0,
            "LOW": 0
        },
        "success_rate": 100.0,
        "analyzed_at": "2025-07-03T10:30:00Z"
    },
    "cards_analysis": [
        {
            "card_id": "507f191e810c19729de860ea",
            "card_name": "Correction bug critique login",
            "criticality_level": "HIGH",
            "analyzed_at": "2025-07-03T10:30:00Z",
            "success": true
        }
    ]
}
```

### 2. Analyse d'une card individuelle

**POST** `/api/trello/card/{card_id}/analyze`

Analyse une seule card.

**Body JSON:**
```json
{
    "name": "Amélioration interface utilisateur",
    "desc": "Revoir le design de la page d'accueil",
    "due": null,
    "list_name": "Backlog",
    "board_id": "507f1f77bcf86cd799439011",
    "board_name": "Projet Principal",
    "labels": [
        {"name": "Enhancement", "color": "blue"}
    ],
    "members": [],
    "url": "https://trello.com/c/..."
}
```

**Réponse:**
```json
{
    "card_id": "507f191e810c19729de860ea",
    "card_name": "Amélioration interface utilisateur",
    "criticality_level": "LOW",
    "analyzed_at": "2025-07-03T10:30:00Z",
    "success": true
}
```

### 3. Analyse en lot (multi-boards)

**POST** `/api/trello/cards/batch-analyze`

Analyse des cards provenant de différents boards.

**Body JSON:**
```json
{
    "cards": [
        {
            "id": "card1",
            "name": "Task 1",
            "desc": "Description...",
            "board_id": "board1",
            "board_name": "Projet A",
            // ... autres champs
        },
        {
            "id": "card2",
            "name": "Task 2", 
            "desc": "Description...",
            "board_id": "board2",
            "board_name": "Projet B",
            // ... autres champs
        }
    ]
}
```

### 4. Vérification de santé du service

**GET** `/api/trello/health`

Vérifie que le service d'analyse est opérationnel.

**Réponse:**
```json
{
    "status": "healthy",
    "service": "Trello Criticality Analyzer",
    "gemini_configured": true,
    "timestamp": "2025-07-03T10:30:00Z"
}
```

## Niveaux de criticité

- **HIGH**: Impact critique sur l'application, blocage majeur, deadline proche
- **MEDIUM**: Impact modéré, peut attendre mais important  
- **LOW**: Impact faible, amélioration ou tâche secondaire

## Configuration requise

1. **Variable d'environnement:** `GOOGLE_API_KEY` (clé API Gemini)
2. **Documents:** Uploader des documents décrivant l'application dans le système de vectorisation
3. **Dépendances:** `google-generativeai==0.4.0`

## Gestion des erreurs

Toutes les APIs retournent des codes d'erreur HTTP appropriés :

- `400`: Données manquantes ou invalides
- `500`: Erreur interne du serveur
- `200`: Succès

En cas d'erreur lors de l'analyse d'une card individuelle, le système retourne un niveau de criticité par défaut (`MEDIUM`) et marque `success: false`.
