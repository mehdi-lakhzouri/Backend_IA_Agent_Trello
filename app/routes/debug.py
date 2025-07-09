"""
Route de debug temporaire pour inspecter ChromaDB.
À supprimer après les tests.
"""

from flask import Blueprint, jsonify, current_app
from app.database.chroma import ChromaDBManager
import traceback

# Blueprint pour les routes de debug
debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/chroma/status', methods=['GET'])
def chroma_status():
    """
    Vérifie le statut de ChromaDB.
    
    Returns:
        JSON: Informations sur l'état de ChromaDB
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Obtenir le nombre total de documents
        count = collection.count()
        
        return jsonify({
            "status": "connected",
            "collection_name": current_app.config['CHROMA_COLLECTION_NAME'],
            "total_documents": count,
            "db_path": current_app.config['CHROMA_DB_PATH']
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la vérification ChromaDB: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@debug_bp.route('/chroma/documents', methods=['GET'])
def list_documents():
    """
    Liste tous les documents dans ChromaDB.
    
    Returns:
        JSON: Liste des documents avec leurs métadonnées
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Récupérer tous les documents
        results = collection.get(
            include=['documents', 'metadatas', 'embeddings']
        )
        
        documents = []
        for i, doc_id in enumerate(results['ids']):
            doc_info = {
                "id": doc_id,
                "metadata": results['metadatas'][i] if results['metadatas'] else {},
                "content_preview": results['documents'][i][:200] + "..." if results['documents'] and len(results['documents'][i]) > 200 else results['documents'][i],
                "content_length": len(results['documents'][i]) if results['documents'] else 0,
                "has_embedding": results['embeddings'] is not None and len(results['embeddings']) > i
            }
            documents.append(doc_info)
        
        return jsonify({
            "total_count": len(documents),
            "documents": documents
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération des documents: {str(e)}")
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@debug_bp.route('/chroma/document/<string:doc_id>', methods=['GET'])
def get_document_details(doc_id):
    """
    Récupère les détails complets d'un document spécifique.
    
    Args:
        doc_id (str): ID du document
        
    Returns:
        JSON: Détails complets du document
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Récupérer le document spécifique
        results = collection.get(
            ids=[doc_id],
            include=['documents', 'metadatas', 'embeddings']
        )
        
        if not results['ids']:
            return jsonify({"error": f"Document avec ID '{doc_id}' non trouvé"}), 404
        
        document = {
            "id": results['ids'][0],
            "metadata": results['metadatas'][0] if results['metadatas'] else {},
            "content": results['documents'][0] if results['documents'] else "",
            "content_length": len(results['documents'][0]) if results['documents'] else 0,
            "embedding_dimensions": len(results['embeddings'][0]) if results['embeddings'] else 0
        }
        
        return jsonify(document), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération du document {doc_id}: {str(e)}")
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@debug_bp.route('/chroma/search/<string:query>', methods=['GET'])
def search_documents(query):
    """
    Recherche des documents par similarité.
    
    Args:
        query (str): Texte de recherche
        
    Returns:
        JSON: Documents similaires trouvés
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Effectuer une recherche par similarité
        results = collection.query(
            query_texts=[query],
            n_results=5,
            include=['documents', 'metadatas', 'distances']
        )
        
        search_results = []
        if results['ids'] and len(results['ids']) > 0:
            for i, doc_id in enumerate(results['ids'][0]):
                result_info = {
                    "id": doc_id,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "content_preview": results['documents'][0][i][:200] + "..." if results['documents'] and len(results['documents'][0][i]) > 200 else results['documents'][0][i],
                    "similarity_distance": results['distances'][0][i] if results['distances'] else None
                }
                search_results.append(result_info)
        
        return jsonify({
            "query": query,
            "results_count": len(search_results),
            "results": search_results
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la recherche '{query}': {str(e)}")
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@debug_bp.route('/chroma/clear', methods=['DELETE'])
def clear_database():
    """
    DANGER: Supprime tous les documents de ChromaDB.
    
    Returns:
        JSON: Confirmation de suppression
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Compter les documents avant suppression
        count_before = collection.count()
        
        # Récupérer tous les IDs et supprimer
        all_docs = collection.get()
        if all_docs['ids']:
            collection.delete(ids=all_docs['ids'])
        
        count_after = collection.count()
        
        return jsonify({
            "message": "Base de données ChromaDB vidée",
            "documents_deleted": count_before,
            "documents_remaining": count_after
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la suppression: {str(e)}")
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
