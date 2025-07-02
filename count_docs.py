#!/usr/bin/env python3
"""
Script simple pour compter les documents dans ChromaDB
Usage: python count_docs.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Ajouter le dossier parent au path
sys.path.append(str(Path(__file__).parent))

# Configuration directe (sans Flask)
CHROMA_DB_PATH = os.environ.get('CHROMA_DB_PATH') or './instance/chromadb'
CHROMA_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION_NAME') or 'documents'

try:
    # Import direct de ChromaDB
    import chromadb
    from chromadb.config import Settings
    
    print("📊 Comptage des documents ChromaDB")
    print("-" * 40)
    
    # Connexion directe à ChromaDB
    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Vérifier si la collection existe
    try:
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
    except Exception:
        print(f"❌ Collection '{CHROMA_COLLECTION_NAME}' non trouvée")
        print("Uploadez d'abord un document pour créer la collection")
        sys.exit(1)
    
    # Compter les documents
    count = collection.count()
    
    print(f"Base de données: {CHROMA_DB_PATH}")
    print(f"Collection: {CHROMA_COLLECTION_NAME}")
    print(f"Nombre de documents: {count}")
    
    if count > 0:
        print("\n📋 Liste des documents:")
        results = collection.get(include=['metadatas'])
        for i, doc_id in enumerate(results['ids'], 1):
            metadata = results['metadatas'][i-1] if results['metadatas'] else {}
            filename = metadata.get('filename', 'Sans nom')
            print(f"  {i}. {doc_id} - {filename}")
    else:
        print("\n💡 Aucun document trouvé. Uploadez un fichier via l'API pour commencer.")
    
except ImportError:
    print("❌ ChromaDB n'est pas installé")
    print("Installez-le avec: pip install chromadb")
except Exception as e:
    print(f"❌ Erreur: {e}")
    print("Assurez-vous que ChromaDB est initialisé et qu'au moins un document a été uploadé.")
