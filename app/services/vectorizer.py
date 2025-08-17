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
            # Calcul du hash du contenu complet pour identification unique
            import hashlib
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            for i, chunk in enumerate(chunks):
                metadata = {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": i,
                    "timestamp": datetime.now().isoformat(),
                    "chunk_size": len(chunk),
                    "total_chunks": len(chunks),
                    "content_hash": content_hash
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
        Vérifie si un fichier existe déjà dans ChromaDB basé sur le hash du contenu.
        Cette stratégie évite les collisions de noms et se base uniquement sur le contenu.
        
        Args:
            filename (str): Nom du fichier (utilisé pour les logs)
            content (str, optional): Contenu du fichier pour vérification par hash
            
        Returns:
            Dict: {
                "exists": bool,
                "document_id": str si trouvé,
                "message": str
            }
        """
        try:
            import hashlib
            
            # Si pas de contenu fourni, impossible de vérifier par hash
            if not content:
                return {
                    "exists": False,
                    "message": "Impossible de vérifier sans contenu - considéré comme nouveau"
                }
            
            collection = self.db_manager.get_collection()
            
            # Calculer le hash du contenu fourni
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            # Recherche par content_hash dans les métadonnées (plus robuste)
            results = collection.get(
                where={"content_hash": content_hash},
                include=['documents', 'metadatas']
            )
            
            if not results['ids']:
                return {
                    "exists": False,
                    "message": f"Contenu unique - aucun doublon détecté pour '{filename}'"
                }
            
            # Si des documents avec le même hash existent
            if results['ids'] and len(results['ids']) > 0:
                # Récupérer les infos du premier document trouvé
                first_metadata = results.get('metadatas', [{}])[0]
                document_id = first_metadata.get("document_id")
                existing_filename = first_metadata.get("filename", "fichier_inconnu")
                
                return {
                    "exists": True,
                    "document_id": document_id,
                    "existing_filename": existing_filename,
                    "message": f"Contenu identique déjà stocké (fichier original: '{existing_filename}')"
                }
            
            # Cas de sécurité
            return {
                "exists": False,
                "message": "Vérification incomplète - considéré comme nouveau"
            }
            
        except Exception as e:
            current_app.logger.error(f"Erreur lors de la vérification de doublon par hash: {str(e)}")
            return {
                "exists": False,
                "message": f"Erreur lors de la vérification: {str(e)}"
            }
