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
        if not file.filename or not isinstance(file.filename, str) or not FileHandler.allowed_file(str(file.filename)):
            return jsonify({
                "error": f"Type de fichier non autorisé. Extensions autorisées: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}"
            }), 400
            
        # Vérification de la taille avant téléchargement
        file_content = file.read()
        file.seek(0)  # Réinitialiser le curseur pour permettre la lecture ultérieure
        
        # Vérifier la taille (max 10 Mo par défaut ou valeur de la config)
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024)  # 10 Mo par défaut
        if len(file_content) > max_size:
            return jsonify({
                "error": f"Fichier trop volumineux. Taille maximale: {max_size / (1024 * 1024):.1f} Mo"
            }), 400
            
        # Générer un nom de fichier unique
        unique_filename, original_secure_name = FileHandler.generate_unique_filename(
            file.filename, 
            file_content
        )
        
        # S'assurer que le dossier d'upload existe
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Sauvegarde du fichier avec le nom unique
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Extraction du contenu
        content = FileHandler.extract_content(filepath)
        if not content:
            # Supprimer le fichier si extraction impossible
            os.remove(filepath)
            return jsonify({"error": "Impossible d'extraire le contenu du fichier"}), 400

        # Vérification de doublon avant vectorisation
        vectorizer = VectorizerService()
        duplicate_info = vectorizer.check_duplicate_file(original_secure_name, content)
        if duplicate_info.get("exists"):
            # Supprimer le fichier si c'est un doublon
            os.remove(filepath)
            return jsonify({
                "error": "Fichier déjà existant",
                "details": duplicate_info
            }), 409  # 409 Conflict
        
        # Vectorisation et stockage
        try:
            # Stocker avec le nom original pour l'affichage, mais en utilisant le fichier avec nom unique
            document_id = vectorizer.vectorize_and_store(content, original_secure_name)
        except Exception as e:
            # Nettoyer en cas d'erreur
            os.remove(filepath)
            current_app.logger.error(f"Erreur lors de la vectorisation/embedding: {str(e)}")
            return jsonify({"error": "Embedding service unavailable, please try again later."}), 503
        
        # Supprimer le fichier temporaire après traitement réussi
        os.remove(filepath)
        
        return jsonify({
            "message": "Document uploadé et vectorisé avec succès",
            "document_id": document_id,
            "original_filename": original_secure_name,
            "system_filename": unique_filename,
            "content_length": len(content)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de l'upload: {str(e)}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@upload_bp.route('/list-files', methods=['GET'])
def list_files():
    """Liste tous les fichiers stockés dans ChromaDB avec leurs statistiques"""
    try:
        from app.database.chroma import ChromaDBManager
        chroma_manager = ChromaDBManager()
        
        # Récupérer tous les documents
        all_docs = chroma_manager.get_all_documents()
        
        # Grouper par filename
        files_stats = {}
        for doc in all_docs:
            filename = doc.get('metadata', {}).get('filename', 'unknown')
            if filename not in files_stats:
                files_stats[filename] = {
                    'filename': filename,
                    'chunks_count': 0,
                    'total_content_length': 0,
                    'document_ids': []
                }
            
            files_stats[filename]['chunks_count'] += 1
            files_stats[filename]['total_content_length'] += len(doc.get('content', ''))
            files_stats[filename]['document_ids'].append(doc.get('id', ''))
        
        return jsonify({
            "total_files": len(files_stats),
            "files": list(files_stats.values())
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors du listing: {str(e)}"}), 500
