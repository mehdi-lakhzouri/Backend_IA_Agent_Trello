import os
import mysql.connector
from mysql.connector import Error
from app.db import db
from app import create_app

class DatabaseService:
    """Service pour automatiser la création de la base de données et des tables"""
    
    def __init__(self):
        self.host = os.getenv('MYSQL_HOST', 'localhost')
        self.user = os.getenv('MYSQL_USER', 'root')
        self.password = os.getenv('MYSQL_PASSWORD', '')
        self.db_name = 'talanagent'
    
    def create_database_if_not_exists(self):
        """Crée la base de données si elle n'existe pas"""
        try:
            connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print(f"Base de données '{self.db_name}' vérifiée/créée.")
            cursor.close()
            connection.close()
            return True
        except Error as e:
            print(f"Erreur lors de la création de la base de données : {e}")
            return False
    
    def create_tables_if_not_exist(self):
        """Crée les tables si elles n'existent pas"""
        try:
            app = create_app()
            with app.app_context():
                db.create_all()
                print("Tables créées/vérifiées avec succès !")
            return True
        except Exception as e:
            print(f"Erreur lors de la création des tables : {e}")
            return False
    
    def ensure_database_and_tables(self):
        """Garantit que la base et les tables existent"""
        if self.create_database_if_not_exists():
            return self.create_tables_if_not_exist()
        return False 