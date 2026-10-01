"""Indexe les documents officiels EnergiePlus avec ChromaDB local.

Cette version évite langchain-community, dont la version installée se ferme
au démarrage. Les documents restent sur le poste et les vecteurs sont locaux.
"""

from __future__ import annotations

import csv
import glob
import hashlib
from pathlib import Path

import chromadb
from docx import Document as WordDocument
from pypdf import PdfReader

from local_embeddings import LocalHashEmbeddings

DOCUMENTS_DIR = Path("./documents")
CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "energieplus_knowledge"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(text: str) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [clean[index:index + CHUNK_SIZE] for index in range(0, len(clean), step) if clean[index:index + CHUNK_SIZE].strip()]


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        return "\n".join(paragraph.text for paragraph in WordDocument(path).paragraphs)
    if suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix == ".csv":
        with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
            rows = []
            for row in csv.DictReader(handle):
                values = []
                for value in row.values():
                    if isinstance(value, list):
                        values.extend(str(item) for item in value if item)
                    elif value:
                        values.append(str(value))
                if values:
                    rows.append(" | ".join(values))
            return "\n".join(rows)
    return ""


def source_region(source: str, text: str) -> str:
    searchable = f"{source} {text}".lower()
    if "wallon" in searchable:
        return "Wallonie"
    if "brux" in searchable or "renolution" in searchable:
        return "Bruxelles-Capitale"
    if "flandr" in searchable or "mijn verbouw" in searchable:
        return "Flandre"
    return "Belgique"


def run_ingestion() -> None:
    print("[INGEST] Lecture des documents régionaux…")
    paths = [Path(item) for item in glob.glob(str(DOCUMENTS_DIR / "**/*"), recursive=True) if Path(item).suffix.lower() in {".txt", ".csv", ".docx", ".pdf"} and Path(item).name != "LAE__RESP_PEB_TAB.csv"]
    records: list[tuple[str, str, str]] = []
    for path in paths:
        try:
            chunks = chunk_text(extract_text(path))
            records.extend((path.name, chunk, source_region(path.name, chunk)) for chunk in chunks)
            print(f"[INGEST] {path.name}: {len(chunks)} extrait(s)")
        except Exception as error:
            print(f"[WARN] Document ignoré ({path.name}) : {error}")

    if not records:
        raise RuntimeError("Aucun contenu exploitable dans ./documents.")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(COLLECTION_NAME)
    embeddings = LocalHashEmbeddings()
    for start in range(0, len(records), 100):
        batch = records[start:start + 100]
        texts = [text for _, text, _ in batch]
        collection.upsert(
            ids=[hashlib.sha256(f"{source}:{index}:{text}".encode("utf-8")).hexdigest() for index, (source, text, _) in enumerate(batch, start)],
            documents=texts,
            metadatas=[{"source": source, "region": region} for source, _, region in batch],
            embeddings=embeddings.embed_documents(texts),
        )
    print(f"[OK] {len(records)} extraits indexés dans ChromaDB ({COLLECTION_NAME}).")


if __name__ == "__main__":
    run_ingestion()
