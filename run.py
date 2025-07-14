"""
Point d'entrée de l'application Flask.
Lance le serveur de développement et initialise l'application.
"""

from app import create_app
import os

# Création de l'instance Flask
app = create_app()

from app.db import db

if __name__ == '__main__':
    # Configuration pour le développement
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
