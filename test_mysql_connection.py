import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Charger les variables d'environnement depuis .env
load_dotenv()

host = os.getenv('MYSQL_HOST', 'localhost')
user = os.getenv('MYSQL_USER', 'root')
password = os.getenv('MYSQL_PASSWORD', '')
database = os.getenv('MYSQL_DB', '')

try:
    connection = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database
    )
    if connection.is_connected():
        print(f"Connexion réussie à la base MySQL '{database}' sur {host} avec l'utilisateur '{user}' !")
        connection.close()
except Error as e:
    print(f"Erreur lors de la connexion à MySQL : {e}") 