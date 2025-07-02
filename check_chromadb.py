#!/usr/bin/env python3
"""
Script pour inspecter ChromaDB - Voir les documents et collections
Usage: python check_chromadb.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration directe (sans Flask)
CHROMA_DB_PATH = os.environ.get('CHROMA_DB_PATH') or './instance/chromadb'
CHROMA_COLLECTION_NAME = os.environ.get('CHROMA_COLLECTION_NAME') or 'documents'

def check_chromadb():
    """Vérifie l'état de ChromaDB et affiche les informations."""
    
    print("🔍 Inspection de ChromaDB")
    print("=" * 50)
    
    try:
        # Import direct de ChromaDB
        import chromadb
        from chromadb.config import Settings
        
        # Informations de configuration
        print(f"📂 Chemin de la base: {CHROMA_DB_PATH}")
        print(f"📋 Nom de la collection: {CHROMA_COLLECTION_NAME}")
        print()
        
        # Vérifier si le dossier existe
        if not os.path.exists(CHROMA_DB_PATH):
            print("❌ Le dossier ChromaDB n'existe pas encore")
            print("   Uploadez d'abord un document pour créer la base")
            return
        
        # Initialiser ChromaDB
        print("🔌 Connexion à ChromaDB...")
        client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Lister toutes les collections
        print("📚 Collections disponibles:")
        collections = client.list_collections()
        
        if not collections:
            print("   ❌ Aucune collection trouvée")
            return
        
        total_docs = 0
        for i, collection in enumerate(collections, 1):
            count = collection.count()
            total_docs += count
            
            print(f"   {i}. Nom: '{collection.name}'")
            print(f"      ID: {collection.id}")
            print(f"      Documents: {count}")
            print()
        
        # Détails de la collection principale
        print("📋 Détails de la collection principale:")
        try:
            main_collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
            doc_count = main_collection.count()
            
            print(f"   Nom: {CHROMA_COLLECTION_NAME}")
            print(f"   Nombre de documents: {doc_count}")
            
            if doc_count > 0:
                print("\n📄 Aperçu des documents:")
                # Récupérer quelques documents pour aperçu
                results = main_collection.get(
                    limit=5,
                    include=['documents', 'metadatas']
                )
                
                for i, doc_id in enumerate(results['ids'], 1):
                    metadata = results['metadatas'][i-1] if results['metadatas'] else {}
                    content = results['documents'][i-1] if results['documents'] else ""
                    
                    print(f"   {i}. ID: {doc_id}")
                    print(f"      Métadonnées: {metadata}")
                    print(f"      Aperçu: {content[:100]}...")
                    print()
                
                if doc_count > 5:
                    print(f"   ... et {doc_count - 5} autres documents")
            
        except Exception as e:
            print(f"   ❌ Erreur lors de l'accès à la collection: {e}")
        
        # Résumé
        print("📊 RÉSUMÉ:")
        print(f"   • Total collections: {len(collections)}")
        print(f"   • Total documents: {total_docs}")
        print(f"   • Base de données: {CHROMA_DB_PATH}")
        
    except ImportError:
        print("❌ ChromaDB n'est pas installé")
        print("Installez-le avec: pip install chromadb")
    except Exception as e:
        print(f"❌ Erreur lors de l'inspection: {e}")
        import traceback
        traceback.print_exc()

def check_database_files():
    """Vérifie les fichiers physiques de la base."""
    print("\n🗂️  Fichiers de la base de données:")
    print("=" * 50)
    
    if os.path.exists(CHROMA_DB_PATH):
        for root, dirs, files in os.walk(CHROMA_DB_PATH):
            level = root.replace(CHROMA_DB_PATH, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                print(f"{subindent}{file} ({size} bytes)")
    else:
        print("❌ Dossier de base de données introuvable")

if __name__ == "__main__":
    print("🚀 Script d'inspection ChromaDB")
    print()
    
    # Vérifier ChromaDB
    check_chromadb()
    
    # Vérifier les fichiers
    check_database_files()
    
    print("\n✅ Inspection terminée!")
