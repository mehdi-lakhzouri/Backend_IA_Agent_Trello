"""
Configuration et gestion de ChromaDB.
Interface pour l'initialisation et les opérations sur la base vectorielle.
"""

from typing import List, Dict, Any, Optional
import os
from datetime import datetime

# Imports ChromaDB et LangChain
import chromadb
from chromadb.config import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

from flask import current_app

class ChromaDBManager:
    """Gestionnaire de la base de données vectorielle ChromaDB."""
    
    def __init__(self):
        """Initialise la connexion à ChromaDB."""
        self.client = None
        self.collection = None
        self.vectorstore = None
        self.embeddings = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialise le client ChromaDB avec embeddings Google."""
        try:
            # Configuration du chemin de la base
            db_path = current_app.config.get('CHROMA_DB_PATH', './instance/chromadb')
            os.makedirs(db_path, exist_ok=True)
            
            # Initialisation des embeddings Google
            api_key = current_app.config.get('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY non configurée")
            
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=api_key
            )
            
            # Initialisation du vectorstore LangChain avec Chroma
            collection_name = current_app.config.get('CHROMA_COLLECTION_NAME', 'IA_AGENT_TALAN')
            
            self.vectorstore = Chroma(
                collection_name=collection_name,
                persist_directory=db_path,
                embedding_function=self.embeddings
            )
            
            current_app.logger.info(f"ChromaDB initialisé avec collection '{collection_name}'")
                
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'initialisation ChromaDB: {str(e)}")
            raise
    
    def store_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """
        Stocke des documents dans ChromaDB via LangChain.
        
        Args:
            documents (List[Dict]): Liste des documents avec contenu et métadonnées
            
        Returns:
            bool: True si le stockage a réussi
        """
        try:
            if self.vectorstore is None:
                current_app.logger.error("ChromaDB non initialisé")
                return False
            
            # Préparation des textes et métadonnées pour LangChain
            texts = []
            metadatas = []
            
            for doc in documents:
                texts.append(doc['content'])
                metadatas.append(doc['metadata'])
            
            # Ajout à la collection via LangChain
            self.vectorstore.add_texts(
                texts=texts,
                metadatas=metadatas
            )
            
            current_app.logger.info(f"Stocké {len(documents)} documents dans ChromaDB")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors du stockage: {str(e)}")
            return False
    
    def similarity_search(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        Recherche par similarité dans ChromaDB via LangChain.
        
        Args:
            query (str): Requête de recherche
            k (int): Nombre de résultats à retourner
            
        Returns:
            List[Dict]: Documents similaires avec scores
        """
        try:
            if self.vectorstore is None:
                current_app.logger.error("ChromaDB non initialisé")
                return []
            
            # Recherche avec scores
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            
            # Formatage des résultats
            formatted_results = []
            for doc, score in results:
                result = {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": 1.0 - score  # ChromaDB retourne des distances, on convertit en similarité
                }
                formatted_results.append(result)
            
            current_app.logger.info(f"Trouvé {len(formatted_results)} résultats pour: {query}")
            return formatted_results
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la recherche: {str(e)}")
            return []
    
    def get_retriever(self, search_kwargs: Optional[Dict[str, Any]] = None):
        """
        Retourne un retriever LangChain pour la chaîne QA.
        
        Args:
            search_kwargs (Dict): Paramètres de recherche
            
        Returns:
            Retriever LangChain
        """
        if self.vectorstore is None:
            raise ValueError("ChromaDB non initialisé")
        if search_kwargs is None:
            search_kwargs = {}
        return self.vectorstore.as_retriever(search_kwargs=search_kwargs)
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la collection.
        
        Returns:
            Dict: Statistiques de la collection
        """
        try:
            if self.vectorstore is None:
                return {
                    "total_documents": 0,
                    "total_chunks": 0,
                    "collection_name": "Non initialisé",
                    "status": "Non initialisé"
                }
            
            # Récupération du client direct pour les stats
            collection_name = current_app.config.get('CHROMA_COLLECTION_NAME', 'IA_AGENT_TALAN')
            
            return {
                "total_documents": "N/A",  # LangChain ne fournit pas facilement ce count
                "total_chunks": "N/A",
                "collection_name": collection_name,
                "status": "Opérationnel",
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "collection_name": "erreur",
                "status": f"Erreur: {str(e)}"
            }
    
    def delete_document(self, document_id: str) -> bool:
        """
        Supprime un document de ChromaDB.
        
        Args:
            document_id (str): ID du document à supprimer
            
        Returns:
            bool: True si la suppression a réussi
        """
        try:
            if self.vectorstore is None:
                current_app.logger.error("ChromaDB non initialisé")
                return False
            
            # LangChain/Chroma ne fournit pas de méthode directe pour supprimer par métadonnées
            # Cette fonctionnalité pourrait nécessiter l'accès direct au client ChromaDB
            current_app.logger.warning("Suppression de documents non implémentée dans cette version")
            return False
                
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la suppression: {str(e)}")
            return False
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Récupère tous les documents stockés dans ChromaDB.
        
        Returns:
            List[Dict]: Liste de tous les documents avec métadonnées
        """
        try:
            if self.vectorstore is None:
                return []
            
            # Utiliser la collection directe pour récupérer tous les documents
            db_path = current_app.config.get('CHROMA_DB_PATH', './instance/chromadb')
            collection_name = current_app.config.get('CHROMA_COLLECTION_NAME', 'IA_AGENT_TALAN')
            
            # Client ChromaDB direct pour plus de contrôle
            client = chromadb.PersistentClient(path=db_path)
            collection = client.get_collection(name=collection_name)
            
            # Récupérer tous les documents
            all_docs = collection.get()
            
            documents = []
            ids = all_docs.get('ids') or []
            docs = all_docs.get('documents') or []
            metas = all_docs.get('metadatas') or []
            embeds = all_docs.get('embeddings') or []
            for i, doc_id in enumerate(ids):
                doc_content = docs[i] if i < len(docs) else 'N/A'
                doc_metadata = metas[i] if i < len(metas) else {}
                embedding_size = len(embeds[i]) if embeds and i < len(embeds) else 0
                doc_info = {
                    'id': doc_id,
                    'content': doc_content,
                    'metadata': doc_metadata,
                    'embedding_size': embedding_size
                }
                documents.append(doc_info)
            
            return documents
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération des documents: {str(e)}")
            return []
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Récupère des informations détaillées sur la collection ChromaDB.
        
        Returns:
            Dict: Informations détaillées sur la collection
        """
        try:
            db_path = current_app.config.get('CHROMA_DB_PATH', './instance/chromadb')
            collection_name = current_app.config.get('CHROMA_COLLECTION_NAME', 'IA_AGENT_TALAN')
            
            # Client ChromaDB direct
            client = chromadb.PersistentClient(path=db_path)
            
            try:
                collection = client.get_collection(name=collection_name)
                count = collection.count()
                
                # Récupérer un échantillon pour analyser la structure
                sample = collection.peek()
                
                return {
                    'collection_name': collection_name,
                    'database_path': db_path,
                    'total_documents': count,
                    'collection_exists': True,
                    'sample_ids': (sample.get('ids') or [])[:5],
                    'embedding_dimension': len((sample.get('embeddings') or [[]])[0]) if len((sample.get('embeddings') or [])) > 0 else 0,
                    'metadata_fields': list((sample.get('metadatas') or [{}])[0].keys()) if len((sample.get('metadatas') or [])) > 0 else [],
                    'status': 'operational'
                }
                
            except Exception as e:
                if "does not exist" in str(e).lower():
                    return {
                        'collection_name': collection_name,
                        'database_path': db_path,
                        'total_documents': 0,
                        'collection_exists': False,
                        'status': 'collection_not_found',
                        'error': str(e)
                    }
                else:
                    raise e
                    
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération des infos collection: {str(e)}")
            return {
                'collection_name': collection_name,
                'database_path': db_path,
                'total_documents': 0,
                'collection_exists': False,
                'status': 'error',
                'error': str(e)
            }
    
    def search_document_by_metadata(self, metadata_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Recherche des documents par métadonnées.
        
        Args:
            metadata_filter (Dict): Filtres de métadonnées
            
        Returns:
            List[Dict]: Documents correspondants
        """
        try:
            if self.vectorstore is None:
                return []
            
            db_path = current_app.config.get('CHROMA_DB_PATH', './instance/chromadb')
            collection_name = current_app.config.get('CHROMA_COLLECTION_NAME', 'IA_AGENT_TALAN')
            
            client = chromadb.PersistentClient(path=db_path)
            collection = client.get_collection(name=collection_name)
            
            # Recherche avec filtre de métadonnées
            results = collection.get(
                where=metadata_filter,
                include=['documents', 'metadatas', 'embeddings']
            )
            
            documents = []
            ids = results.get('ids') or []
            docs = results.get('documents') or []
            metas = results.get('metadatas') or []
            embeds = results.get('embeddings') or []
            for i, doc_id in enumerate(ids):
                doc_content = docs[i] if i < len(docs) else 'N/A'
                doc_metadata = metas[i] if i < len(metas) else {}
                embedding_size = len(embeds[i]) if embeds and i < len(embeds) else 0
                doc_info = {
                    'id': doc_id,
                    'content': doc_content,
                    'metadata': doc_metadata,
                    'embedding_size': embedding_size
                }
                documents.append(doc_info)
            
            return documents
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la recherche par métadonnées: {str(e)}")
            return []

    def get_collection(self):
        """
        Retourne la collection ChromaDB brute (client direct).
        Utile pour les opérations avancées ou accès direct.
        """
        db_path = current_app.config.get('CHROMA_DB_PATH', './instance/chromadb')
        collection_name = current_app.config.get('CHROMA_COLLECTION_NAME', 'IA_AGENT_TALAN')
        client = chromadb.PersistentClient(path=db_path)
        return client.get_collection(name=collection_name)

   
