"""
Service de cryptage pour sécuriser les tokens Trello.
Utilise la bibliothèque cryptography avec Fernet pour un cryptage symétrique sécurisé.
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoService:
    """Service de cryptage/décryptage pour les tokens sensibles."""
    
    def __init__(self):
        """Initialise le service avec une clé dérivée de la variable d'environnement."""
        self._fernet = self._get_fernet_instance()
    
    def _get_fernet_instance(self):
        """Crée une instance Fernet avec une clé dérivée."""
        # Récupérer la clé secrète depuis les variables d'environnement
        secret_key = os.environ.get('CRYPTO_SECRET_KEY', 'default-secret-key-change-in-production')
        
        # Convertir en bytes
        secret_key_bytes = secret_key.encode()
        
        # Dériver une clé appropriée pour Fernet
        salt = b'trello_tokens_salt'  # En production, utilisez un salt aléatoire stocké séparément
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key_bytes))
        
        return Fernet(key)
    
    def encrypt_token(self, token: str) -> str:
        """
        Crypte un token Trello.
        
        Args:
            token (str): Le token à crypter
            
        Returns:
            str: Le token crypté en base64
        """
        if not token:
            raise ValueError("Le token ne peut pas être vide")
        
        try:
            # Convertir en bytes et crypter
            token_bytes = token.encode('utf-8')
            encrypted_bytes = self._fernet.encrypt(token_bytes)
            
            # Retourner en base64 pour stockage en DB
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Erreur lors du cryptage du token: {str(e)}")
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Décrypte un token Trello crypté.
        
        Args:
            encrypted_token (str): Le token crypté en base64
            
        Returns:
            str: Le token décrypté en clair
        """
        if not encrypted_token:
            raise ValueError("Le token crypté ne peut pas être vide")
        
        try:
            # Décoder du base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
            
            # Décrypter
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            
            # Retourner en string
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            raise Exception(f"Erreur lors du décryptage du token: {str(e)}")
    
    def is_token_encrypted(self, token: str) -> bool:
        """
        Vérifie si un token est déjà crypté.
        
        Args:
            token (str): Le token à vérifier
            
        Returns:
            bool: True si le token semble crypté, False sinon
        """
        try:
            # Essayer de décrypter - si ça marche, c'est crypté
            self.decrypt_token(token)
            return True
        except:
            # Si échec, ce n'est probablement pas crypté
            return False


# Instance globale du service
crypto_service = CryptoService()
