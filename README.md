# 🤖 Microservice IA RAG ÉnergiePlus (Python FastAPI)

Ce dossier contient le service d'Intelligence Artificielle basé sur le **RAG (Retrieval-Augmented Generation)** interconnecté avec le backend **Spring Boot** de la plateforme Énergie.

---

## 🚀 Démarrage Rapide (En 3 étapes)

### Étape 1 : Créer l'environnement Python et installer les dépendances
Dans le dossier `ai_service` :
```bash
# 1. Créer l'environnement virtuel
python -m venv venv

# 2. Activer l'environnement (Windows)
.\venv\Scripts\activate

# 3. Installer les bibliothèques
pip install -r requirements.txt
```

### Étape 2 : Ajouter votre Clé API OpenAI (Optionnel)
Créez un fichier `.env` dans ce dossier `ai_service/` :
```env
OPENAI_API_KEY=sk-proj-votre-cle-api-openai-ici
SPRING_BOOT_URL=http://localhost:8080
AI_API_KEY=dev-ai-api-key-change-me
```

### Étape 3 : Lancer le service RAG IA
```bash
python app.py
```
Le service démarrera sur **`http://localhost:8000`** (Documentation FastAPI Swagger disponible sur `http://localhost:8000/docs`).

---

## 📁 Comment ajouter vos documents PDF pour l'entraînement RAG

Déposez tous vos fichiers `.pdf` ou `.txt` (ex: fiches produits, lois PEB Wallonie/Bruxelles/Flandre, tableaux de primes) dans le dossier :
`ai_service/documents/`

Puis lancez l'ingestion dans la base vectorielle :
```bash
python ingest.py
```
Les vecteurs créés seront automatiquement sauvegardés dans `ai_service/chroma_db/` !
