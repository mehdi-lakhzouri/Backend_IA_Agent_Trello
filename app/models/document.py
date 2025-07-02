"""
Schémas de données et modèles Pydantic.
Définit les structures de données utilisées par l'API.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime

class QuestionRequest(BaseModel):
    """Modèle pour les requêtes de questions à l'IA."""
    
    question: str = Field(..., min_length=1, max_length=1000, description="Question à poser à l'IA")
    context: Optional[str] = Field(None, max_length=2000, description="Contexte additionnel pour la question")
    
    @validator('question')
    def validate_question(cls, v):
        """Valide que la question n'est pas vide."""
        if not v.strip():
            raise ValueError('La question ne peut pas être vide')
        return v.strip()
    
    @validator('context')
    def validate_context(cls, v):
        """Valide le contexte s'il est fourni."""
        if v is not None:
            return v.strip()
        return v

class DocumentInfo(BaseModel):
    """Modèle pour les informations d'un document."""
    
    document_id: str = Field(..., description="Identifiant unique du document")
    filename: str = Field(..., description="Nom du fichier")
    content_length: int = Field(..., ge=0, description="Longueur du contenu en caractères")
    upload_timestamp: datetime = Field(default_factory=datetime.now, description="Date d'upload")
    file_size: Optional[int] = Field(None, ge=0, description="Taille du fichier en bytes")
    file_extension: Optional[str] = Field(None, description="Extension du fichier")
    
class UploadResponse(BaseModel):
    """Modèle pour la réponse d'upload."""
    
    message: str = Field(..., description="Message de statut")
    document_id: str = Field(..., description="ID du document uploadé")
    filename: str = Field(..., description="Nom du fichier traité")
    content_length: int = Field(..., ge=0, description="Longueur du contenu extrait")
    
class QuestionResponse(BaseModel):
    """Modèle pour la réponse à une question."""
    
    question: str = Field(..., description="Question posée")
    answer: str = Field(..., description="Réponse de l'IA")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Sources utilisées")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Score de confiance")
    processing_time: float = Field(default=0.0, ge=0.0, description="Temps de traitement en secondes")

class DocumentChunk(BaseModel):
    """Modèle pour un chunk de document vectorisé."""
    
    chunk_id: str = Field(..., description="Identifiant unique du chunk")
    document_id: str = Field(..., description="ID du document parent")
    content: str = Field(..., description="Contenu du chunk")
    chunk_index: int = Field(..., ge=0, description="Index du chunk dans le document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées du chunk")

class ErrorResponse(BaseModel):
    """Modèle pour les réponses d'erreur."""
    
    error: str = Field(..., description="Message d'erreur")
    details: Optional[Dict[str, Any]] = Field(None, description="Détails supplémentaires")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp de l'erreur")

class HealthResponse(BaseModel):
    """Modèle pour la réponse de santé de l'API."""
    
    status: str = Field(..., description="Statut de l'API")
    message: str = Field(..., description="Message de statut")
    version: Optional[str] = Field("1.0.0", description="Version de l'API")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp du check")

class ConfigInfo(BaseModel):
    """Modèle pour les informations de configuration."""
    
    max_file_size: int = Field(..., description="Taille maximale des fichiers en bytes")
    allowed_extensions: List[str] = Field(..., description="Extensions de fichiers autorisées")
    upload_folder: str = Field(..., description="Dossier de stockage des uploads")
    
class DatabaseStats(BaseModel):
    """Modèle pour les statistiques de la base de données."""
    
    total_documents: int = Field(default=0, ge=0, description="Nombre total de documents")
    total_chunks: int = Field(default=0, ge=0, description="Nombre total de chunks")
    collection_name: str = Field(..., description="Nom de la collection ChromaDB")
    last_update: Optional[datetime] = Field(None, description="Dernière mise à jour")

# Schemas pour la validation des données d'entrée
class FileUploadSchema:
    """Schema de validation pour l'upload de fichiers."""
    
    @staticmethod
    def validate_file_type(filename: str, allowed_extensions: set) -> bool:
        """Valide le type de fichier."""
        if not filename:
            return False
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    @staticmethod
    def validate_file_size(file_size: int, max_size: int) -> bool:
        """Valide la taille du fichier."""
        return 0 < file_size <= max_size

# Utilitaires pour la sérialisation
def serialize_datetime(dt: datetime) -> str:
    """Sérialise une datetime en string ISO."""
    return dt.isoformat()

def deserialize_datetime(dt_str: str) -> datetime:
    """Désérialise une string ISO en datetime."""
    return datetime.fromisoformat(dt_str)
