# 🤖 Talan Agent - Analyseur IA de Criticité Trello

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-orange.svg)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4.24-purple.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

> **Analyseur intelligent de criticité pour cartes Trello utilisant l'IA Google Gemini avec contexte documentaire et historique d'analyse**

## 📖 Description

**Talan Agent** est une solution d'intelligence artificielle avancée qui révolutionne la gestion des projets Trello en analysant automatiquement la criticité des cartes. Grâce à l'intégration de Google Gemini 2.5 Flash, ChromaDB et un système de vectorisation intelligent, l'application fournit des analyses contextuelles précises basées sur :

- 📚 **Documents d'application** uploadés et vectorisés
- 🧠 **Historique d'analyses** des cartes similaires
- 🎯 **Contexte métier** spécifique à chaque board Trello
- ⚡ **Traitement en batch** optimisé pour les grandes listes

### 🎯 Cas d'usage principaux

- **Product Owners** : Priorisation automatique des backlogs
- **Tech Leads** : Identification rapide des bugs critiques
- **Équipes Agile** : Classification intelligente des user stories
- **Support Client** : Évaluation automatique de l'urgence des tickets

## ✨ Fonctionnalités principales

### 🔍 **Analyse de criticité intelligente**
- Classification en 3 niveaux : **HIGH** / **MEDIUM** / **LOW**
- Analyse contextuelle basée sur la documentation projet
- Prise en compte des échéances, labels et membres assignés
- Réanalyse avec vérification approfondie

### 📄 **Gestion documentaire avancée**
- Upload et vectorisation de documents (.txt)
- Stockage intelligent dans ChromaDB
- Recherche sémantique dans la base documentaire
- Purge et gestion des collections

### 🔄 **Intégration Trello complète**
- Analyse de cartes individuelles ou en batch
- Configuration par board avec règles spécifiques
- Ajout automatique de labels de criticité
- Commentaires automatiques avec justification IA
- Déplacement de cartes selon la criticité

### 📊 **Monitoring et statistiques**
- Historique complet des analyses
- Distribution de criticité par board/liste
- Métriques de performance et usage
- Logs détaillés avec rotation automatique

## 🏗️ Architecture du projet

```
backend/
├── 🐍 run.py                    # Point d'entrée Flask
├── 🐳 Dockerfile               # Conteneurisation
├── 🔧 docker-compose.yml       # Orchestration des services
├── 📦 requirements.txt         # Dépendances Python
├── ⚙️ alembic.ini             # Configuration des migrations DB
│
├── 📁 app/                     # Application Flask principale
│   ├── 🔧 __init__.py         # Factory pattern & configuration CORS
│   ├── ⚙️ config.py           # Configuration environnements
│   ├── 🗄️ db.py               # Configuration SQLAlchemy
│   │
│   ├── 📁 routes/              # Endpoints API REST
│   │   ├── 🔄 trello.py       # API Trello & analyse criticité
│   │   ├── 📤 upload.py       # Upload & vectorisation documents
│   │   └── 🔍 inspect.py      # Inspection ChromaDB
│   │
│   ├── 📁 services/            # Logique métier
│   │   ├── 🤖 criticality_analyzer.py    # Moteur IA Gemini
│   │   ├── 🎼 analysis_orchestrator.py   # Orchestration analyses
│   │   ├── 🔄 trello_service.py          # Client API Trello
│   │   ├── 📊 vectorizer.py              # Service vectorisation
│   │   ├── 💾 database_service.py        # Accès données
│   │   └── 📈 statistics_service.py      # Métriques & stats
│   │
│   ├── 📁 models/              # Modèles de données
│   │   ├── 🗃️ document.py     # Modèles documents
│   │   └── 📋 trello_models.py # Modèles Trello & analyses
│   │
│   ├── 📁 database/            # Couche persistance
│   │   └── 🧊 chroma.py        # Gestionnaire ChromaDB
│   │
│   └── 📁 utils/               # Utilitaires
│       ├── 🔐 crypto_service.py # Chiffrement tokens
│       └── 📁 file_handler.py   # Gestion fichiers
│
├── 📁 tools/                   # Outils Trello automatisés
│   ├── 🏷️ add_etiquette_tool.py # Ajout labels criticité
│   ├── 💬 add_comment_tool.py   # Commentaires automatiques
│   └── ↔️ move_card_tool.py     # Déplacement cartes
│
├── 📁 migrations/              # Migrations base de données Alembic
├── 📁 logs/                    # Logs applicatifs rotatifs
├── 📁 docs/                    # Documentation technique
└── 📁 instance/                # Données runtime (uploads, ChromaDB)
```

### 🛠️ Stack technologique

| Couche | Technologies |
|--------|-------------|
| **Backend** | ![Python](https://img.shields.io/badge/Python-3.9-blue) ![Flask](https://img.shields.io/badge/Flask-2.3.3-green) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.41-red) |
| **IA & ML** | ![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-orange) ![LangChain](https://img.shields.io/badge/LangChain-0.1.14-yellow) |
| **Vectorisation** | ![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4.24-purple) ![Embeddings](https://img.shields.io/badge/Embeddings-Vector%20Search-lightblue) |
| **Base de données** | ![MySQL](https://img.shields.io/badge/MySQL-8.0-blue) ![Alembic](https://img.shields.io/badge/Alembic-Migrations-green) |
| **Intégrations** | ![Trello API](https://img.shields.io/badge/Trello-API%20REST-blue) ![Google AI](https://img.shields.io/badge/Google%20AI-Studio-red) |
| **DevOps** | ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED) ![Gunicorn](https://img.shields.io/badge/Gunicorn-WSGI-green) |

## 🚀 Installation

### 📋 Prérequis

- **Python 3.9+** 
- **Docker & Docker Compose** (recommandé)
- **MySQL 8.0+** (si installation locale)
- **Clé API Google Gemini** ([Google AI Studio](https://makersuite.google.com/))
- **Token API Trello** ([Trello Developer](https://trello.com/app-key))

### 🔧 Installation avec Docker (Recommandée)

1. **Cloner le repository**
```bash
git clone https://github.com/mehdi-lakhzouri/Backend_IA_Agent_Trello.git
cd Backend_IA_Agent_Trello
```

2. **Configuration environnement**
```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer les variables d'environnement
nano .env
```

3. **Variables d'environnement essentielles**
```env
# Configuration Google Gemini AI
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Configuration MySQL
MYSQL_HOST=mysql
MYSQL_DB=talanagent
MYSQL_USER=dev_user
MYSQL_PASSWORD=dev_pwd

# Configuration Flask
SECRET_KEY=your_super_secret_key_here
FLASK_ENV=development

# Configuration analyse
ANALYSIS_BATCH_SIZE=8
MAX_CONTENT_LENGTH=16777216
#configuration trello 
TRELLO_API_KEY=TRELLO-API-KEY
TRELLO_API_SECRET=TRELLO-SECRET-API
TRELLO_APP_NAME=APP-NAME
# Chemins de stockage
UPLOAD_FOLDER=./instance/uploaded_files
CHROMA_DB_PATH=./instance/chromadb
```

4. **Démarrage des services**
```bash
# Lancement complet (MySQL + Flask + PHPMyAdmin)
docker-compose up -d

# Vérification des services
docker-compose ps
```

5. **Initialisation de la base de données**
```bash
# Exécution des migrations
docker-compose exec flask-app python -m flask db upgrade

# Vérification de l'état
docker-compose logs flask-app
```

### 🖥️ Installation locale

1. **Environnement Python**
```bash
# Création environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Installation des dépendances
pip install -r requirements.txt
```

2. **Configuration base de données**
```bash
# Installation MySQL local
# Créer la base de données 'talanagent'
# Configurer les variables d'environnement MySQL

# Migrations
flask db upgrade
```

3. **Démarrage de l'application**
```bash
python run.py
```

## ⚡ Démarrage rapide

### 1. 🔑 Configuration des tokens

```bash
# Test de connexion Gemini
curl -X POST http://localhost:5000/api/test-gemini \
  -H "Content-Type: application/json"
```

### 2. 📄 Upload de documentation

```bash
# Upload d'un document de contexte
curl -X POST http://localhost:5000/fileapi/upload \
  -F "file=@mon_cahier_des_charges.txt"
```

### 3. 🔍 Analyse d'une carte Trello

```bash
# Analyse de criticité d'une carte
curl -X POST http://localhost:5000/api/trello/card/CARD_ID/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bug critique sur le login",
    "desc": "Les utilisateurs ne peuvent plus se connecter",
    "board_id": "BOARD_ID",
    "board_name": "Projet Principal",
    "due": "2025-08-20T10:00:00.000Z"
  }'
```

### 4. 📊 Analyse d'une liste complète

```bash
# Analyse de toutes les cartes d'une liste
curl -X POST http://localhost:5000/api/trello/board/BOARD_ID/list/LIST_ID/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_TRELLO_TOKEN",
    "board_name": "Mon Board",
    "list_name": "To Do"
  }'
```

## 🐳 Déploiement

### Docker Production

1. **Configuration production**
```bash
# Fichier .env.production
FLASK_ENV=production
FLASK_DEBUG=0
```

2. **Build & déploiement**
```bash
# Build de l'image de production
docker build -t talan-agent:latest .

# Déploiement avec docker-compose
docker-compose -f docker-compose.prod.yml up -d
```


## 📚 Utilisation

### 🔍 **API d'analyse de criticité**

#### Analyse d'une carte individuelle
```http
POST /api/trello/card/{card_id}/analyze
Content-Type: application/json

{
  "name": "Titre de la carte",
  "desc": "Description détaillée",
  "board_id": "board_id",
  "board_name": "Nom du board",
  "list_name": "Nom de la liste",
  "due": "2025-08-20T10:00:00.000Z",
  "labels": [{"name": "bug", "color": "red"}],
  "members": [{"fullName": "John Doe"}]
}
```

**Réponse:**
```json
{
  "status": "success",
  "data": {
    "card_id": "507f191e810c19729de860ea",
    "card_name": "Bug critique sur le login",
    "criticality_level": "HIGH",
    "justification": "Critical user authentication issue affecting all users with immediate business impact requiring urgent resolution.",
    "analyzed_at": "2025-08-17T15:30:00Z",
    "success": true
  }
}
```

#### Analyse d'une liste complète
```http
POST /api/trello/board/{board_id}/list/{list_id}/analyze
Content-Type: application/json

{
  "token": "trello_api_token",
  "board_name": "Projet Principal",
  "list_name": "Backlog"
}
```

### 📄 **API de gestion documentaire**

#### Upload de documents
```http
POST /fileapi/upload
Content-Type: multipart/form-data

file: cahier_des_charges.txt
```

#### Liste des documents
```http
GET /fileapi/list-files
```

### 📊 **API d'inspection et statistiques**

#### Statistiques ChromaDB
```http
GET /api/inspect/stats
```

#### Recherche dans les documents
```http
POST /api/inspect/search
Content-Type: application/json

{
  "query": "authentification utilisateur",
  "n_results": 5
}
```

### 🔧 **Configuration des boards**

#### Ajout d'une configuration board
```http
POST /api/trello/config-board-subscription
Content-Type: application/json

{
  "board_id": "board_id",
  "board_name": "Mon Board",
  "token": "trello_token",
  "list_id": "list_id_high_priority",
  "list_name": "High Priority",
  "move_high_cards": true,
  "add_labels": true,
  "add_comments": true
}
```

## 🧪 Tests

### Tests unitaires
```bash
# Installation des dépendances de test
pip install pytest pytest-flask

# Exécution des tests
pytest tests/

# Tests avec couverture
pytest --cov=app tests/
```

### Tests d'intégration
```bash
# Tests des endpoints API
pytest tests/test_api_endpoints.py -v

# Tests de l'analyseur de criticité
pytest tests/test_criticality_analyzer.py -v
```

### Tests manuels avec Postman
```bash
# Collection Postman disponible dans /docs/postman/
# Import dans Postman pour tests complets de l'API
```

## 🤝 Contribution

### 🔄 Workflow de développement

1. **Fork du repository**
```bash
git fork https://github.com/mehdi-lakhzouri/Backend_IA_Agent_Trello.git
```

2. **Création d'une branche feature**
```bash
git checkout -b feature/nouvelle-fonctionnalite
```

3. **Développement avec tests**
```bash
# Ajout de tests pour nouvelles fonctionnalités
pytest tests/test_nouvelle_fonctionnalite.py

# Vérification du code
flake8 app/
black app/
```

4. **Pull Request**
- Description claire de la fonctionnalité
- Tests passants
- Documentation mise à jour

### 📝 **Conventions de code**

- **PEP 8** pour le style Python
- **Type hints** pour les fonctions publiques
- **Docstrings** pour les modules et classes
- **Tests unitaires** pour toute nouvelle fonctionnalité

### 🐛 **Reporting de bugs**

Utilisez les [Issues GitHub](https://github.com/mehdi-lakhzouri/Backend_IA_Agent_Trello/issues) avec :
- Description détaillée du problème
- Étapes de reproduction
- Logs d'erreur
- Environnement (OS, Python, Docker...)


## 🙏 Remerciements & Crédits

### 🌟 **Technologies open source**
- **[Google Gemini](https://gemini.google.com/)** - Moteur d'intelligence artificielle
- **[ChromaDB](https://www.trychroma.com/)** - Base de données vectorielle
- **[Flask](https://flask.palletsprojects.com/)** - Framework web Python
- **[LangChain](https://langchain.com/)** - Framework pour applications LLM

t

### 🏢 **Organisations**
- **[Talan](https://talan.com/)** - Support entreprise et vision produit
- **Community Contributors** - Améliorer continues et feedback

---

<div align="center">

**⭐ Si ce projet vous aide, n'hésitez pas à lui donner une étoile !**

[![GitHub stars](https://img.shields.io/github/stars/mehdi-lakhzouri/Backend_IA_Agent_Trello.svg?style=social&label=Star)](https://github.com/mehdi-lakhzouri/Backend_IA_Agent_Trello)
[![GitHub forks](https://img.shields.io/github/forks/mehdi-lakhzouri/Backend_IA_Agent_Trello.svg?style=social&label=Fork)](https://github.com/mehdi-lakhzouri/Backend_IA_Agent_Trello/fork)

**Développé avec ❤️ par l'équipe Talan Agent**

</div>
