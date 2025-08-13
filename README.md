 # Backend_IA_Agent_Trello

## Description
Ce projet est un backend Flask conçu pour analyser les cartes Trello en utilisant un modèle de langage avancé (LLM) pour évaluer leur criticité. Le système a été optimisé pour effectuer des analyses par lot afin d'améliorer les performances et réduire la latence.

## Structure des fichiers

### Fichiers principaux

- **`agent_analyse.py`** : Script principal pour exécuter l'analyse des cartes Trello.
- **`run.py`** : Point d'entrée pour démarrer le serveur Flask.
- **`requirements.txt`** : Liste des dépendances Python nécessaires pour exécuter le projet.
- **`alembic.ini`** : Fichier de configuration pour gérer les migrations de base de données avec Alembic.

### Dossier `app`

#### Sous-dossier `config`
- **`config.py`** : Contient les configurations globales de l'application.

#### Sous-dossier `database`
- **`chroma.py`** : Gestion des interactions avec la base de données Chroma.

#### Sous-dossier `models`
- **`document.py`** : Modèle de données pour représenter les documents analysés.
- **`trello_models.py`** : Modèle de données pour représenter les entités Trello (cartes, listes, etc.).

#### Sous-dossier `routes`
- **`inspect.py`** : Route pour inspecter les données.
- **`trello.py`** : Route pour gérer les intégrations avec l'API Trello.
- **`upload.py`** : Route pour gérer les fichiers uploadés.

#### Sous-dossier `services`
- **`criticality_analyzer.py`** : Service pour analyser la criticité des cartes Trello. Inclut une méthode `analyze_cards_batch` pour l'analyse par lot.
- **`database_service.py`** : Service pour interagir avec la base de données.
- **`trello_service.py`** : Service pour interagir avec l'API Trello.
- **`vectorizer.py`** : Service pour vectoriser les données des cartes Trello.
- **`analysis_orchestrator.py`** : Orchestrateur pour gérer l'analyse des cartes Trello, y compris l'analyse par lot et les actions associées.

#### Sous-dossier `utils`
- **`crypto_service.py`** : Service pour gérer les opérations cryptographiques.
- **`file_handler.py`** : Service pour gérer les fichiers uploadés.

### Dossier `migrations`
- Contient les fichiers nécessaires pour gérer les migrations de base de données avec Alembic.

### Dossier `instance`
- Contient les données spécifiques à l'instance, comme les fichiers de base de données SQLite.

### Dossier `tools`
- **`add_comment_tool.py`** : Outil pour ajouter des commentaires aux cartes Trello.
- **`add_etiquette_tool.py`** : Outil pour ajouter des étiquettes aux cartes Trello.
- **`move_card_tool.py`** : Outil pour déplacer des cartes Trello entre les listes.

## Analyse par lot

### Contexte
L'analyse par lot a été introduite pour optimiser le processus d'évaluation des cartes Trello. Au lieu d'analyser chaque carte individuellement, les cartes sont regroupées en lots, ce qui réduit le nombre d'appels au modèle de langage et améliore les performances globales.

### Fonctionnement
1. **Regroupement des cartes** : Les cartes Trello sont regroupées en lots de taille configurable.
2. **Analyse par le LLM** : Chaque lot est envoyé au modèle de langage pour une analyse collective.
3. **Traitement des résultats** : Les résultats de l'analyse sont traités et persistés dans la base de données.
4. **Actions Trello** : Les actions nécessaires (comme le déplacement des cartes ou l'ajout de commentaires) sont effectuées en fonction des résultats de l'analyse.

### Avantages
- **Réduction de la latence** : Moins d'appels au modèle de langage.
- **Efficacité accrue** : Meilleure utilisation des ressources.
- **Scalabilité** : Le système peut gérer un grand nombre de cartes sans compromettre les performances.

## Configuration
- Assurez-vous que toutes les dépendances listées dans `requirements.txt` sont installées.
- Configurez les variables d'environnement nécessaires dans `app/config/config.py`.

## Exécution
- Pour démarrer le serveur Flask :
  ```bash
  python run.py
  ```
- Pour exécuter une analyse manuelle :
  ```bash
  python agent_analyse.py
  ```

## Contributions
Les contributions sont les bienvenues. Veuillez soumettre une pull request avec une description claire des modifications apportées.

## Licence
Ce projet est sous licence MIT.