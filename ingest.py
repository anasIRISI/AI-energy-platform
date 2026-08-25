import os
import sys
import glob

# Fix encodage console Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Disable symlinks warning on Windows for huggingface
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_DIR = "./documents"
CHROMA_DIR = "./chroma_db"

def load_docx_documents(directory):
    """Charge tous les fichiers .docx du dossier."""
    docx_docs = []
    try:
        import docx
        from langchain_core.documents import Document
        docx_files = glob.glob(os.path.join(directory, "**/*.docx"), recursive=True)
        for filepath in docx_files:
            try:
                doc = docx.Document(filepath)
                text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                if text.strip():
                    docx_docs.append(Document(page_content=text, metadata={"source": filepath}))
            except Exception as fe:
                print(f"[WARN] Erreur lecture fichier docx {filepath} : {fe}")
    except ImportError:
        print("[WARN] python-docx non installe, fichiers .docx ignores.")
    except Exception as e:
        print(f"[WARN] Chargement DOCX : {e}")
    return docx_docs

def get_embeddings():
    """Retourne l'objet d'embeddings selon la configuration (HuggingFace local par défaut ou OpenAI)."""
    provider = os.getenv("EMBEDDING_PROVIDER", "huggingface").lower()
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if provider == "openai" and openai_key and not openai_key.startswith("your_"):
        print("[INGEST] Utilisation de l'API OpenAI Embeddings...")
        try:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(openai_api_key=openai_key)
        except Exception as e:
            print(f"[WARN] Erreur initialisation OpenAI ({e}), bascule vers les Embeddings locaux gratuits.")

    print("[INGEST] Utilisation des Embeddings locaux HuggingFace (all-MiniLM-L6-v2) - 100% Gratuit & Illimite...")
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    except Exception:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def run_ingestion():
    print("[INGEST] Debut de l'ingestion des documents RAG...")
    if not os.path.exists(DOCUMENTS_DIR):
        os.makedirs(DOCUMENTS_DIR)
        print(f"[INGEST] Creation du dossier {DOCUMENTS_DIR}")

    docs = []

    # 1. Chargeur TXT
    try:
        txt_loader = DirectoryLoader(DOCUMENTS_DIR, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
        txt_docs = txt_loader.load()
        docs.extend(txt_docs)
        if txt_docs:
            print(f"[INGEST] {len(txt_docs)} fichier(s) TXT charge(s).")
    except Exception as e:
        print(f"[WARN] Chargement TXT : {e}")

    # 2. Chargeur CSV
    try:
        csv_files = glob.glob(os.path.join(DOCUMENTS_DIR, "**/*.csv"), recursive=True)
        for cf in csv_files:
            try:
                from langchain_community.document_loaders import CSVLoader
                loader = CSVLoader(file_path=cf, encoding="utf-8")
                docs.extend(loader.load())
                print(f"[INGEST] Fichier CSV charge : {os.path.basename(cf)}")
            except Exception as e_csv:
                print(f"[WARN] CSV {cf} : {e_csv}")
    except Exception as e:
        print(f"[WARN] Chargement CSV : {e}")

    # 3. Chargeur DOCX (Word)
    docx_docs = load_docx_documents(DOCUMENTS_DIR)
    if docx_docs:
        docs.extend(docx_docs)
        print(f"[INGEST] {len(docx_docs)} fichier(s) DOCX charge(s).")

    # 4. Chargeur PDF
    try:
        from langchain_community.document_loaders import PyPDFLoader
        pdf_loader = DirectoryLoader(DOCUMENTS_DIR, glob="**/*.pdf", loader_cls=PyPDFLoader)
        pdf_docs = pdf_loader.load()
        docs.extend(pdf_docs)
        if pdf_docs:
            print(f"[INGEST] {len(pdf_docs)} page(s)/document(s) PDF charge(s).")
    except ImportError:
        print("[WARN] pypdf non disponible, les fichiers PDF seront ignores.")
    except Exception as e:
        print(f"[WARN] Chargement PDF : {e}")

    if not docs:
        print("[ERREUR] Aucun document trouve dans ./documents. Ajoutez vos PDF/TXT/DOCX et relancez ingest.py.")
        return

    print(f"[INGEST] Total : {len(docs)} document(s)/page(s) charge(s). Decoupage en blocs (chunks)...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = text_splitter.split_documents(docs)
    print(f"[INGEST] {len(chunks)} blocs crees.")

    embeddings = get_embeddings()
    
    print(f"[INGEST] Generation des vecteurs et enregistrement dans ChromaDB ({CHROMA_DIR})...")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )
    print(f"[OK] Ingestion terminee avec succes ! {len(chunks)} blocs vectorises dans {CHROMA_DIR}")

if __name__ == "__main__":
    run_ingestion()
