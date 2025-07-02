"""
Service de vectorisation avec LangChain et ChromaDB.
Gère l'extraction, la vectorisation et le stockage des documents.
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

# Imports LangChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from app.database.chroma import ChromaDBManager
from flask import current_app

class VectorizerService:
    """Service de vectorisation des documents."""
    
    def __init__(self):
        """Initialise le service de vectorisation."""
        self.db_manager = ChromaDBManager()
        self.text_splitter = self._initialize_text_splitter()
    
    def _initialize_text_splitter(self):
        """Initialise le splitter de texte LangChain."""
        return RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def vectorize_and_store(self, content: str, filename: str) -> str:
        """
        Vectorise le contenu d'un document et le stocke dans ChromaDB.
        
        Args:
            content (str): Contenu textuel du document
            filename (str): Nom du fichier source
            
        Returns:
            str: ID unique du document stocké
        """
        try:
            # Génération d'un ID unique pour le document
            document_id = str(uuid.uuid4())
            
            # Division du texte en chunks avec LangChain
            chunks = self.text_splitter.split_text(content)
            
            # Création des métadonnées pour chaque chunk
            documents = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": i,
                    "timestamp": datetime.now().isoformat(),
                    "chunk_size": len(chunk),
                    "total_chunks": len(chunks)
                }
                documents.append({
                    "content": chunk,
                    "metadata": metadata
                })
            
            # Stockage dans ChromaDB
            success = self.db_manager.store_documents(documents)
            
            if success:
                current_app.logger.info(f"Document {filename} vectorisé avec succès. ID: {document_id}, Chunks: {len(chunks)}")
                return document_id
            else:
                raise Exception("Échec du stockage dans ChromaDB")
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la vectorisation: {str(e)}")
            raise
    
    def search_similar_documents(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """
        Recherche les documents similaires à une requête.
        
        Args:
            query (str): Requête de recherche
            k (int): Nombre de résultats à retourner
            
        Returns:
            List[Dict]: Documents similaires avec scores et métadonnées
        """
        try:
            results = self.db_manager.similarity_search(query, k=k)
            current_app.logger.info(f"Recherche '{query}' - {len(results)} résultats trouvés")
            return results
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la recherche: {str(e)}")
            raise
    
    def get_document_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la base vectorielle.
        
        Returns:
            Dict: Statistiques (nombre de documents, chunks, etc.)
        """
        try:
            return self.db_manager.get_collection_stats()
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
            raise
    
    def check_duplicate_file(self, filename: str, content: Optional[str] = None) -> Dict[str, Any]:
        """
        Vérifie si un fichier existe déjà dans ChromaDB.
        
        Args:
            filename (str): Nom du fichier à vérifier
            content (str, optional): Contenu du fichier pour vérification plus précise
            
        Returns:
            Dict: {
                "exists": bool,
                "documents": List[Dict] si trouvé,
                "message": str
            }
        """
        try:
            collection = self.db_manager.get_collection()
            
            # Recherche par nom de fichier dans les métadonnées
            results = collection.get(
                where={"filename": filename},
                include=['documents', 'metadatas']
            )
            
            if not results['ids']:
                return {
                    "exists": False,
                    "documents": [],
                    "message": f"Aucun fichier trouvé avec le nom '{filename}'"
                }
            
            # Si un contenu est fourni, vérification plus précise
            if content:
                # Reconstituer le contenu original de chaque document trouvé
                documents_found = {}
                for i, doc_id in enumerate(results['ids']):
                    metadatas = results.get('metadatas') or []
                    docs = results.get('documents') or []
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    document_id = metadata.get('document_id')
                    
                    if document_id not in documents_found:
                        documents_found[document_id] = {
                            'chunks': [],
                            'metadata': metadata
                        }
                    
                    documents_found[document_id]['chunks'].append({
                        'index': metadata.get('chunk_index', 0),
                        'content': docs[i] if i < len(docs) else ''
                    })
                
                # Vérifier si le contenu correspond
                for doc_id, doc_data in documents_found.items():
                    # Trier les chunks par index et reconstituer
                    sorted_chunks = sorted(doc_data['chunks'], key=lambda x: x['index'])
                    reconstructed_content = ''.join([chunk['content'] for chunk in sorted_chunks])
                    
                    # Comparaison du contenu (en ignorant les espaces de fin)
                    if reconstructed_content.strip() == content.strip():
                        return {
                            "exists": True,
                            "message": "Le fichier existe déjà"
                        }
                return {
                    "exists": True,
                    "message": "Le fichier existe déjà"
                }
            
            # Retour simple si pas de vérification de contenu
            return {
                "exists": True,
                "message": "Le fichier existe déjà"
            }
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la vérification de doublon: {str(e)}")
            return {
                "exists": False,
                "documents": [],
                "message": f"Erreur lors de la vérification: {str(e)}"
            }
