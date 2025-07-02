"""
Route pour l'upload et le traitement des documents.
Endpoint POST /api/upload pour recevoir et vectoriser les fichiers.
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os

# Services
from app.services.vectorizer import VectorizerService
from app.utils.file_handler import FileHandler

# Blueprint pour les routes d'upload
upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload', methods=['POST'])
def upload_document():
    """
    Upload et vectorisation d'un document.
    Returns:
        JSON: Statut de l'upload et informations du document traité
    """
    try:
        # Vérification de la présence du fichier
        if 'file' not in request.files:
            return jsonify({"error": "Aucun fichier fourni"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "Nom de fichier vide"}), 400
        
        # Validation du fichier
        if not FileHandler.allowed_file(file.filename):
            return jsonify({
                "error": f"Type de fichier non autorisé. Extensions autorisées: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}"
            }), 400
        
        # Sauvegarde sécurisée du fichier
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extraction du contenu
        content = FileHandler.extract_content(filepath)
        if not content:
            return jsonify({"error": "Impossible d'extraire le contenu du fichier"}), 400

        # Vérification de doublon avant vectorisation
        vectorizer = VectorizerService()
        duplicate_info = vectorizer.check_duplicate_file(filename, content)
        if duplicate_info.get("exists"):
            return jsonify({
                "error": "Fichier déjà existant",
                "details": duplicate_info
            }), 409  # 409 Conflict
        
        # Vectorisation et stockage
        document_id = vectorizer.vectorize_and_store(content, filename)
        
        # Nettoyage du fichier temporaire (optionnel)
        # os.remove(filepath)
        
        return jsonify({
            "message": "Document uploadé et vectorisé avec succès",
            "document_id": document_id,
            "filename": filename,
            "content_length": len(content)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'upload: {str(e)}")
        return jsonify({"error": "Erreur interne du serveur"}), 500
