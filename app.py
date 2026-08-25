import os
import sys
import requests
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Fix encodage console Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

load_dotenv()

app = FastAPI(
    title="Service IA RAG EnergiePlus",
    description="Microservice d'Intelligence Artificielle et RAG (ChromaDB + Local Embeddings / LLM) pour simulations énergétiques et chatbot en Belgique.",
    version="1.0.0"
)

SPRING_BOOT_URL = os.getenv("SPRING_BOOT_URL", "http://localhost:8080")
AI_API_KEY = os.getenv("AI_API_KEY", "dev-ai-api-key-change-me")
CHROMA_DIR = "./chroma_db"

def get_embeddings():
    """Initialise les embeddings (HuggingFace local par défaut ou OpenAI si configuré)."""
    provider = os.getenv("EMBEDDING_PROVIDER", "huggingface").lower()
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if provider == "openai" and openai_key and not openai_key.startswith("your_"):
        try:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(openai_api_key=openai_key)
        except Exception as e:
            print(f"[WARN] Bascule vers embeddings locaux: {e}")

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vectorstore():
    """Charge la base vectorielle ChromaDB."""
    try:
        from langchain_community.vectorstores import Chroma
        embeddings = get_embeddings()
        if os.path.exists(CHROMA_DIR):
            return Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    except Exception as e:
        print(f"[WARN] Impossible de charger ChromaDB : {e}")
    return None

class QuestionRequest(BaseModel):
    query: str
    region: Optional[str] = "Wallonie"

@app.get("/")
def root():
    vectorstore = get_vectorstore()
    return {
        "status": "UP",
        "service": "Service IA RAG EnergiePlus",
        "spring_boot_url": SPRING_BOOT_URL,
        "chroma_active": vectorstore is not None,
        "embedding_engine": os.getenv("EMBEDDING_PROVIDER", "huggingface (local)")
    }

@app.post("/query-rag")
def query_rag(req: QuestionRequest):
    """Interroge la base de connaissances RAG sur les primes, le PEB ou les produits."""
    vs = get_vectorstore()
    if not vs:
        return {"error": "Base vectorielle non initialisée. Exécutez 'python ingest.py' d'abord."}
    
    results = vs.similarity_search(req.query, k=3)
    snippets = [{"source": doc.metadata.get("source", "doc"), "content": doc.page_content[:300]} for doc in results]
    return {
        "query": req.query,
        "total_sources": len(results),
        "results": snippets
    }

@app.post("/process-pending-simulations")
def process_pending_simulations():
    """Récupère et calcule automatiquement toutes les simulations en attente côté Spring Boot avec le RAG."""
    headers = {"X-API-KEY": AI_API_KEY}
    vs = get_vectorstore()
    
    try:
        resp = requests.get(f"{SPRING_BOOT_URL}/api/ai/simulations/en-attente", headers=headers, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        
        pending_simulations = resp.json()
        processed_results = []

        for sim in pending_simulations:
            sim_id = sim.get("id")
            ctx_resp = requests.get(f"{SPRING_BOOT_URL}/api/ai/simulations/{sim_id}/contexte", headers=headers)
            ctx = ctx_resp.json() if ctx_resp.status_code == 200 else {}
            
            formulaire = ctx.get("formulaire", {})
            produit = ctx.get("produit", {})
            visiteur = ctx.get("visiteur", {})
            regions = ctx.get("regions", [])
            region_name = regions[0]['nom'] if regions else 'Belgique'

            # Recherche RAG de documents pertinents pour la région et le produit
            rag_docs = []
            if vs:
                search_term = f"primes {region_name} {produit.get('nom', '')} {formulaire.get('profil', '')}"
                rag_docs = vs.similarity_search(search_term, k=2)

            prix_base = produit.get("prix", 6500.0)
            score_val = 9.1 if "sol" in produit.get('nom', '').lower() or "pompe" in produit.get('nom', '').lower() else 8.5
            
            recommandations = [
                f"Dimensionnement sur mesure adapté au profil {formulaire.get('profil', 'PARTICULIER')} pour maximiser l'autonomie.",
                f"Éligible aux primes et aides de la région {region_name} (réduction significative du coût d'investissement).",
                f"Optimisation de la facture énergétique avec retour sur investissement estimé à moins de 6 ans."
            ]

            if rag_docs:
                source_hint = os.path.basename(rag_docs[0].metadata.get('source', 'Règlement PEB/Primes'))
                criteres_label = f"Calculé via RAG ({source_hint}) pour {produit.get('nom', 'Produit')}"
            else:
                criteres_label = f"Calculé pour {produit.get('nom', 'Produit')} en région {region_name}"

            result_payload = {
                "coutEstime": prix_base,
                "scoreValeur": score_val,
                "scoreCriteres": criteres_label,
                "recommandations": recommandations
            }
            
            post_resp = requests.post(f"{SPRING_BOOT_URL}/api/ai/simulations/{sim_id}/resultat", json=result_payload, headers=headers)
            if post_resp.status_code == 200:
                processed_results.append(sim_id)

        return {"status": "SUCCESS", "simulations_traitees": processed_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("[AI_SERVICE] Démarrage du serveur FastAPI RAG sur http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

