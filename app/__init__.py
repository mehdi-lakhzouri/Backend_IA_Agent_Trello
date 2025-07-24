"""
Initialisation de l'application Flask.
Configure CORS, blueprints, scheduler et paramètres globaux.
"""

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
from app.db import db
from flask_migrate import Migrate

def create_app():
    # Centraliser les logs Flask dans le même fichier que agent_analyse
    import logging
    from logging.handlers import RotatingFileHandler
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = f"agent_analyse_{__import__('datetime').datetime.now().strftime('%Y%m%d')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    flask_logger = logging.getLogger('werkzeug')
    app_logger = logging.getLogger()
    # Éviter les doublons
    if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == log_filepath for h in app_logger.handlers):
        file_handler = RotatingFileHandler(
            log_filepath,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        app_logger.addHandler(file_handler)
        flask_logger.addHandler(file_handler)
        app_logger.setLevel(logging.DEBUG)
        flask_logger.setLevel(logging.INFO)
    """Factory pattern pour créer l'instance Flask."""
    
    # Charger les variables d'environnement
    load_dotenv()
    
    # Créer l'instance Flask
    app = Flask(__name__, instance_relative_config=True)
    
    # Configuration CORS
    CORS(app, resources={
        r"/fileapi/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"]
        },
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Configuration de l'application
    app.config.from_object('app.config.Config')
    
    # Créer les dossiers nécessaires
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['CHROMA_DB_PATH'], exist_ok=True)
    
    # Initialiser la base de données
    db.init_app(app)

    # Initialiser Flask-Migrate
    migrate = Migrate(app, db)
    
    # Enregistrement des blueprints
    from app.routes import register_blueprints
    register_blueprints(app)
    
    # Gestion d'erreurs globales
    @app.errorhandler(413)
    def too_large(e):
        return {"error": "File too large. Maximum size is 16MB."}, 413
    
    @app.errorhandler(400)
    def bad_request(e):
        return {"error": "Bad request. Please check your data."}, 400
    
    @app.errorhandler(500)
    def internal_error(error):
        return {"error": "Internal server error. Please try again later."}, 500
    
    return app
