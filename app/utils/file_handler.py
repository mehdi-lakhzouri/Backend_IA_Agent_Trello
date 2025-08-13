"""
Utilitaires pour la gestion des fichiers.
Validation, lecture et traitement des fichiers uploadés.
"""

import os
import uuid
import hashlib
from datetime import datetime
from typing import Optional, Set, Tuple
from werkzeug.utils import secure_filename
from flask import current_app

# Pour le moment, on ne traite que les fichiers TXT

class FileHandler:
    """Gestionnaire de fichiers pour l'application."""
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """
        Vérifie si l'extension du fichier est autorisée.
        
        Args:
            filename (str): Nom du fichier à vérifier
            
        Returns:
            bool: True si l'extension est autorisée
        """
        if not filename:
            return False
        
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    @staticmethod
    def get_file_extension(filename: str) -> Optional[str]:
        """
        Extrait l'extension d'un fichier.
        
        Args:
            filename (str): Nom du fichier
            
        Returns:
            Optional[str]: Extension en minuscules ou None
        """
        if not filename or '.' not in filename:
            return None
        return filename.rsplit('.', 1)[1].lower()
    
    @staticmethod
    def extract_content(filepath: str) -> Optional[str]:
        """
        Extrait le contenu textuel d'un fichier TXT.
        
        Args:
            filepath (str): Chemin vers le fichier
            
        Returns:
            Optional[str]: Contenu textuel ou None en cas d'erreur
        """
        if not os.path.exists(filepath):
            current_app.logger.error(f"Fichier introuvable: {filepath}")
            return None
        
        try:
            extension = FileHandler.get_file_extension(filepath)
            
            if extension == 'txt':
                return FileHandler._extract_text(filepath)
            else:
                current_app.logger.warning(f"Type de fichier non supporté: {extension}. Seuls les fichiers .txt sont autorisés.")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Erreur lors de l'extraction du contenu: {str(e)}")
            return None
    
    @staticmethod
    def _extract_text(filepath: str) -> str:
        """Extrait le contenu d'un fichier texte."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    
    @staticmethod
    def validate_file_size(filepath: str, max_size: int) -> bool:
        """
        Valide la taille d'un fichier.
        
        Args:
            filepath (str): Chemin vers le fichier
            max_size (int): Taille maximale en bytes
            
        Returns:
            bool: True si la taille est acceptable
        """
        try:
            file_size = os.path.getsize(filepath)
            return file_size <= max_size
        except OSError:
            return False
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """
        Nettoie et sécurise un nom de fichier.
        
        Args:
            filename (str): Nom de fichier original
            
        Returns:
            str: Nom de fichier sécurisé
        """
        # Utilisation de secure_filename de Werkzeug
        secure_name = secure_filename(filename)
        
        # Vérifications additionnelles
        if not secure_name:
            secure_name = "unnamed_file"
        
        return secure_name
        
    @staticmethod
    def generate_unique_filename(original_filename: str, file_content: bytes = None) -> Tuple[str, str]:
        """
        Génère un nom de fichier unique basé sur UUID, timestamp et hash du contenu.
        
        Args:
            original_filename (str): Nom de fichier original
            file_content (bytes, optional): Contenu du fichier pour générer un hash
            
        Returns:
            Tuple[str, str]: (Nom unique, extension)
        """
        # Obtenir l'extension sécurisée
        ext = FileHandler.get_file_extension(original_filename) or "txt"
        secure_name = FileHandler.clean_filename(original_filename)
        
        # Générer un UUID
        unique_id = str(uuid.uuid4())
        
        # Ajouter un timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Calculer un hash du contenu si disponible
        content_hash = ""
        if file_content:
            content_hash = hashlib.md5(file_content).hexdigest()[:8]
            unique_filename = f"{timestamp}_{unique_id}_{content_hash}.{ext}"
        else:
            unique_filename = f"{timestamp}_{unique_id}.{ext}"
            
        return unique_filename, secure_name
    
    @staticmethod
    def get_file_info(filepath: str) -> dict:
        """
        Retourne les informations d'un fichier.
        
        Args:
            filepath (str): Chemin vers le fichier
            
        Returns:
            dict: Informations du fichier
        """
        try:
            stat_info = os.stat(filepath)
            return {
                "filename": os.path.basename(filepath),
                "size": stat_info.st_size,
                "extension": FileHandler.get_file_extension(filepath),
                "created": stat_info.st_ctime,
                "modified": stat_info.st_mtime
            }
        except OSError as e:
            current_app.logger.error(f"Erreur lors de la récupération des infos fichier: {str(e)}")
            return {}
