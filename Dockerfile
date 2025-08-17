# ================================
# DOCKERFILE POUR DÉVELOPPEMENT
# Image Python 3.9 slim pour minimiser la taille
# ================================

FROM python:3.9-slim

# ================================
# MÉTADONNÉES
# ================================
LABEL maintainer="Talan Agent Development Team"
LABEL description="Flask app for Trello analysis with ChromaDB - Development Environment"

# ================================
# VARIABLES D'ENVIRONNEMENT
# ================================
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=development
ENV FLASK_DEBUG=1

# ================================
# INSTALLATION DES DÉPENDANCES SYSTÈME
# ================================
RUN apt-get update && apt-get install -y \
    # Dépendances pour MySQL
    default-libmysqlclient-dev \
    pkg-config \
    gcc \
    # Outils de base
    curl \
    && rm -rf /var/lib/apt/lists/*

# ================================
# CONFIGURATION DU RÉPERTOIRE DE TRAVAIL
# ================================
WORKDIR /app

# ================================
# INSTALLATION DES DÉPENDANCES PYTHON
# Copie requirements.txt en premier pour optimiser le cache Docker
# ================================
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ================================
# COPIE DU CODE SOURCE
# ================================
COPY . .

# ================================
# CRÉATION DES DOSSIERS NÉCESSAIRES
# ================================
RUN mkdir -p /app/chroma_data && \
    mkdir -p /app/instance/uploaded_files && \
    mkdir -p /app/logs

# ================================
# PERMISSIONS
# ================================
RUN chmod +x /app/run.py

# ================================
# EXPOSITION DU PORT
# ================================
EXPOSE 5000

# ================================
# COMMANDE PAR DÉFAUT
# Le docker-compose.yml override cette commande
# ================================
CMD ["python", "run.py"]
