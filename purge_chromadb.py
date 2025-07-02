import chromadb
import os

# Paramètres par défaut (adapter si besoin)
DB_PATH = './instance/chromadb'
COLLECTION_NAME = 'IA_AGENT_TALAN'

def purge_chromadb():
    try:
        # Initialisation du client ChromaDB
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        all_ids = collection.get().get('ids', [])
        if all_ids:
            collection.delete(ids=all_ids)
            print(f"{len(all_ids)} documents supprimés de la collection '{COLLECTION_NAME}'.")
        else:
            print(f"Aucun document à supprimer dans la collection '{COLLECTION_NAME}'.")
    except Exception as e:
        print(f"Erreur lors de la purge: {e}")

if __name__ == "__main__":
    purge_chromadb()
