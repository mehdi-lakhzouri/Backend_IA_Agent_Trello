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


@upload_bp.route('/cleanup-duplicates', methods=['POST'])
def cleanup_duplicates():
    """Nettoie les fichiers dupliqués dans ChromaDB"""
    try:
        from app.database.chroma import ChromaDBManager
        chroma_manager = ChromaDBManager()
        
        # Récupérer tous les documents
        all_docs = chroma_manager.get_all_documents()
        
        # Grouper par filename
        files_by_name = {}
        for doc in all_docs:
            filename = doc.get('metadata', {}).get('filename', 'unknown')
            if filename not in files_by_name:
                files_by_name[filename] = []
            files_by_name[filename].append(doc)
        
        # Identifier et supprimer les doublons
        deleted_count = 0
        kept_files = []
        
        for filename, docs in files_by_name.items():
            if len(docs) > 1:
                # Garder le premier groupe de chunks, supprimer les autres
                docs_to_keep = []
                docs_to_delete = []
                
                # Identifier les groupes de chunks (même upload)
                chunks_groups = {}
                for doc in docs:
                    chunk_id = doc.get('metadata', {}).get('chunk_id', 0)
                    upload_time = doc.get('metadata', {}).get('timestamp', 'unknown')
                    
                    group_key = f"{filename}_{upload_time}"
                    if group_key not in chunks_groups:
                        chunks_groups[group_key] = []
                    chunks_groups[group_key].append(doc)
                
                # Garder seulement le premier groupe
                groups_list = list(chunks_groups.values())
                if len(groups_list) > 1:
                    docs_to_keep = groups_list[0]
                    for group in groups_list[1:]:
                        docs_to_delete.extend(group)
                
                # Supprimer les doublons
                for doc in docs_to_delete:
                    doc_id = doc.get('id')
                    if doc_id:
                        chroma_manager.delete_document(doc_id)
                        deleted_count += 1
                
                kept_files.append({
                    'filename': filename,
                    'kept_chunks': len(docs_to_keep),
                    'deleted_chunks': len(docs_to_delete)
                })
            else:
                kept_files.append({
                    'filename': filename,
                    'kept_chunks': len(docs),
                    'deleted_chunks': 0
                })
        
        return jsonify({
            "message": "Nettoyage terminé avec succès",
            "total_deleted_chunks": deleted_count,
            "files_processed": len(files_by_name),
            "details": kept_files
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Erreur lors du nettoyage: {str(e)}"}), 500


@upload_bp.route('/delete-file/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Supprime complètement un fichier spécifique de ChromaDB"""
    try:
        from app.database.chroma import ChromaDBManager
        chroma_manager = ChromaDBManager()
        
        # Récupérer tous les documents du fichier
        all_docs = chroma_manager.get_all_documents()
        docs_to_delete = [doc for doc in all_docs 
                         if doc.get('metadata', {}).get('filename') == filename]
        
        deleted_count = 0
        for doc in docs_to_delete:
            doc_id = doc.get('id')
            if doc_id:
                chroma_manager.delete_document(doc_id)
                deleted_count += 1
        
        if deleted_count > 0:
            return jsonify({
                "message": f"Fichier '{filename}' supprimé avec succès",
                "deleted_chunks": deleted_count
            }), 200
        else:
            return jsonify({"error": f"Fichier '{filename}' non trouvé"}), 404
            
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la suppression: {str(e)}"}), 500
