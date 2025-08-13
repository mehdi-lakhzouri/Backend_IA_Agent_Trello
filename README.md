# Projet Dockerisé

Ce projet utilise Docker pour faciliter le déploiement et le développement.

## Prérequis

- Docker
- Docker Compose

## Utilisation

### Construire et lancer l'application

```bash
# Construire l'image Docker
docker build -t mon-app .

# Ou utiliser Docker Compose
docker-compose up --build
```

### Commandes utiles

```bash
# Lancer en arrière-plan
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter les conteneurs
docker-compose down

# Reconstruire les images
docker-compose build --no-cache
```

## Structure Docker

- `Dockerfile` : Configuration de l'image Docker
- `docker-compose.yml` : Orchestration des services
- `.dockerignore` : Fichiers à exclure lors de la construction

L'application sera accessible sur `http://localhost:4173`