"""
API simple pour inspecter ChromaDB via Postman.
Endpoints pour voir documents et collections.
"""

from flask import Blueprint, jsonify, current_app, request
from app.database.chroma import ChromaDBManager
import traceback

# Blueprint pour l'inspection ChromaDB
inspect_bp = Blueprint('inspect', __name__)

@inspect_bp.route('/collections', methods=['GET'])
def get_collections():
    """
    Liste toutes les collections ChromaDB.
    
    Returns:
        JSON: Liste des collections disponibles
    """
    try:
        chroma_manager = ChromaDBManager()
        client = chroma_manager.client
        
        # Obtenir toutes les collections
        collections = client.list_collections()
        
        collection_info = []
        for collection in collections:
            try:
                count = collection.count()
                collection_info.append({
                    "name": collection.name,
                    "id": collection.id,
                    "document_count": count
                })
            except Exception as e:
                collection_info.append({
                    "name": collection.name,
                    "id": collection.id,
                    "document_count": "erreur",
                    "error": str(e)
                })
        
        return jsonify({
            "total_collections": len(collection_info),
            "collections": collection_info
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": f"Erreur lors de la récupération des collections: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500

@inspect_bp.route('/documents', methods=['GET'])
def get_all_documents():
    """
    Liste tous les documents dans la collection principale.
    
    Returns:
        JSON: Tous les documents avec métadonnées
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Obtenir tous les documents
        results = collection.get(include=['documents', 'metadatas'])
        
        documents = []
        for i, doc_id in enumerate(results['ids']):
            doc = {
                "id": doc_id,
                "metadata": results['metadatas'][i] if results['metadatas'] else {},
                "content_preview": results['documents'][i][:150] + "..." if results['documents'] and len(results['documents'][i]) > 150 else results['documents'][i],
                "content_length": len(results['documents'][i]) if results['documents'] else 0
            }
            documents.append(doc)
        
        return jsonify({
            "collection_name": current_app.config['CHROMA_COLLECTION_NAME'],
            "total_documents": len(documents),
            "documents": documents
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": f"Erreur lors de la récupération des documents: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500

@inspect_bp.route('/document/<string:doc_id>', methods=['GET'])
def get_document(doc_id):
    """
    Récupère un document spécifique par son ID.
    
    Args:
        doc_id: ID du document
        
    Returns:
        JSON: Document complet avec contenu et métadonnées
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Récupérer le document
        results = collection.get(
            ids=[doc_id], 
            include=['documents', 'metadatas']
        )
        
        if not results['ids']:
            return jsonify({"error": f"Document '{doc_id}' non trouvé"}), 404
        
        document = {
            "id": results['ids'][0],
            "metadata": results['metadatas'][0] if results['metadatas'] else {},
            "content": results['documents'][0] if results['documents'] else "",
            "content_length": len(results['documents'][0]) if results['documents'] else 0
        }
        
        return jsonify(document), 200
        
    except Exception as e:
        return jsonify({
            "error": f"Erreur lors de la récupération du document: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500

@inspect_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Statistiques générales sur ChromaDB.
    
    Returns:
        JSON: Statistiques de la base de données
    """
    try:
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Statistiques de base
        total_docs = collection.count()
        
        # Obtenir quelques exemples de métadonnées
        sample_results = collection.get(limit=5, include=['metadatas'])
        
        metadata_keys = set()
        for metadata in sample_results.get('metadatas', []):
            if metadata:
                metadata_keys.update(metadata.keys())
        
        stats = {
            "collection_name": current_app.config['CHROMA_COLLECTION_NAME'],
            "total_documents": total_docs,
            "database_path": current_app.config['CHROMA_DB_PATH'],
            "metadata_fields": list(metadata_keys),
            "status": "active"
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({
            "error": f"Erreur lors du calcul des statistiques: {str(e)}",
            "status": "error",
            "traceback": traceback.format_exc()
        }), 500

@inspect_bp.route('/search', methods=['POST'])
def search_documents():
    """
    Recherche de documents par similarité.
    
    Expected JSON:
        {
            "query": "texte de recherche",
            "limit": 5
        }
    
    Returns:
        JSON: Documents trouvés par similarité
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({"error": "Le champ 'query' est requis"}), 400
        
        query = data['query']
        limit = data.get('limit', 5)
        
        chroma_manager = ChromaDBManager()
        collection = chroma_manager.get_collection()
        
        # Recherche par similarité
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            include=['documents', 'metadatas', 'distances']
        )
        
        search_results = []
        if results['ids'] and len(results['ids']) > 0:
            for i, doc_id in enumerate(results['ids'][0]):
                result = {
                    "id": doc_id,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "content_preview": results['documents'][0][i][:200] + "..." if results['documents'] and len(results['documents'][0][i]) > 200 else results['documents'][0][i],
                    "similarity_score": 1 - results['distances'][0][i] if results['distances'] else None,
                    "distance": results['distances'][0][i] if results['distances'] else None
                }
                search_results.append(result)
        
        return jsonify({
            "query": query,
            "results_found": len(search_results),
            "results": search_results
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": f"Erreur lors de la recherche: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500
