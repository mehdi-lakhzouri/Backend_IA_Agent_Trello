"""
Initialisation de l'application Flask.
Configure CORS, blueprints et paramètres globaux.
"""

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

def create_app():
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
        }
    })
    
    # Configuration de l'application
    app.config.from_object('app.config.Config')
    
    # Créer les dossiers nécessaires
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['CHROMA_DB_PATH'], exist_ok=True)
    
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
