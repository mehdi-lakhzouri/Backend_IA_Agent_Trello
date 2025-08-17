import chromadb
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Chemin vers le dossier contenant la base ChromaDB
DB_PATH = os.environ.get('CHROMA_DB_PATH') or os.path.join('.', 'instance', 'chromadb')

def purge_all_collections():
    try:
        # Initialiser le client ChromaDB en mode persistant
        client = chromadb.PersistentClient(path=DB_PATH)

        # Liste toutes les collections existantes
        collections = client.list_collections()

        if not collections:
            print("✅ Aucune collection à supprimer.")
            return

        # Suppression de chaque collection
        for col in collections:
            client.delete_collection(name=col.name)
            print(f"🗑️ Collection '{col.name}' supprimée avec succès.")

        print("✅ Toutes les collections ont été purgées.")
        
    except Exception as e:
        print(f"❌ Erreur lors de la purge : {e}")

if __name__ == "__main__":
    purge_all_collections()
