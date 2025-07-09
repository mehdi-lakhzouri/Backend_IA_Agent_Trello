"""
Configuration globale de l'application Flask.
Définit les paramètres pour développement, test et production.
"""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class Config:
    """Configuration de base."""
    
    # Sécurité
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Upload de fichiers
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or './instance/uploaded_files'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {'txt'}  
    
    # Configuration ChromaDB
    CHROMA_DB_PATH = os.environ.get('CHROMA_DB_PATH') or './instance/chromadb'
    CHROMA_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION_NAME') or 'documents'
    
    # Configuration API Gemini
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-1.5-flash'
    
    # Configuration serveur
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '0.0.0.0')
    
    # Validation de la configuration
    @staticmethod
    def validate_config():
        """Valide que toutes les variables nécessaires sont configurées."""
        if not Config.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY doit être définie dans les variables d'environnement")
        return True

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER', 'root')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', 'localhost')}/{os.getenv('MYSQL_DB', 'talanagent')}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Configuration pour l'environnement de développement."""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Configuration pour l'environnement de production."""
    DEBUG = False
    FLASK_ENV = 'production'

class TestConfig(Config):
    """Configuration pour les tests."""
    TESTING = True
    UPLOAD_FOLDER = './instance/test_uploads'
    CHROMA_DB_PATH = './instance/test_chromadb'

# Sélection de la configuration selon l'environnement
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': DevelopmentConfig
}
