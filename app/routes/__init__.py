"""
Initialisation et enregistrement des blueprints.
Centralise l'enregistrement de toutes les routes de l'application.
"""

from flask import Blueprint

def register_blueprints(app):
    """Enregistre tous les blueprints de l'application."""
    
    # Import des blueprints
    from app.routes.upload import upload_bp
    
    # Enregistrement des blueprints
    app.register_blueprint(upload_bp, url_prefix='/fileapi')
    
    # Blueprint principal pour les routes générales
    main_bp = Blueprint('main', __name__)
    
    @main_bp.route('/')
    def index():
        """Route racine de l'API."""
        return {
            "message": "Backend IA - API Ready",
            "version": "1.0.0",
            "endpoints": {
                "upload": {
                    "method": "POST", 
                    "url": "/fileapi/upload",
                    "description": "Upload et vectorisation de documents TXT",
                    "content-type": "multipart/form-data",
                    "accepted_files": "txt"
                }
            },
            "features": [
                "📤 Upload de documents TXT uniquement",
                "🔍 Vectorisation automatique avec Google Embeddings",
                "💾 Stockage dans ChromaDB"
            ]
        }
    
    app.register_blueprint(main_bp)
