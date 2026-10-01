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

### Étape 2 : Configurer le service
Copiez `.env.example` vers `.env` dans ce dossier :
```env
SPRING_BOOT_URL=http://localhost:8080
AI_API_KEY=dev-ai-api-key-change-me
EMBEDDING_PROVIDER=local
GEMINI_API_KEY=votre_cle_gemini
GEMINI_SIMULATION_MODEL=gemini-3.5-flash-lite
SIMULATION_WORKER_ENABLED=true
SIMULATION_POLL_INTERVAL_SECONDS=20
```

Le RAG reste local. Gemini reçoit seulement le produit, la région et les réponses énergie nécessaires à une simulation, jamais les coordonnées du visiteur.

### Étape 3 : Construire l'index RAG et lancer le service IA

Les sources nécessaires au RAG sont versionnées dans `documents/`. Après un
clone ou un `git pull`, reconstruisez la base vectorielle locale :

```bash
python ingest.py
```

Puis démarrez le service sur le port utilisé par le front-end :

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8081
```
Le service démarre sur **`http://localhost:8081`**. Le worker traite automatiquement les simulations `EN_ATTENTE` toutes les 20 secondes ; consultez `http://localhost:8081/worker-status` pour vérifier son activité. L'endpoint `POST /process-pending-simulations` reste disponible pour un déclenchement manuel d'administration.

---

## 🔄 Après un clone ou un `git pull`

Pour obtenir un environnement IA fonctionnel sur une nouvelle machine :

```bash
# Récupère aussi les livrables lourds stockés dans Git LFS
git lfs install
git lfs pull

# Crée l'environnement Python et installe les dépendances
python -m venv venv
# Windows : .\venv\Scripts\activate
pip install -r requirements.txt

# Crée .env depuis .env.example, puis renseigne GEMINI_API_KEY
# Reconstruit la base vectorielle à partir des sources versionnées
python ingest.py

# Lance l'API IA
python -m uvicorn app:app --host 127.0.0.1 --port 8081
```

### Fichiers indispensables à la simulation

- `app.py`, `ingest.py`, `local_embeddings.py` et `requirements.txt` : code du service.
- `documents/` : sources réglementaires et techniques utilisées par le RAG. Ce dossier reste dans Git standard et doit toujours être conservé.
- `.env` : configuration locale non versionnée ; copiez `.env.example` et fournissez vos propres clés.
- `chroma_db/` : index local généré par `python ingest.py`. Il n'est pas versionné et peut toujours être reconstruit depuis `documents/`.

Les rapports PFA, PDF, DOCX, ZIP et captures de validation sont conservés dans Git LFS. Ils restent disponibles après `git lfs pull`, mais ne sont pas nécessaires à l'exécution de la simulation.

---

## 📁 Comment ajouter vos documents PDF pour l'entraînement RAG

Déposez tous vos fichiers `.pdf` ou `.txt` (ex: fiches produits, lois PEB Wallonie/Bruxelles/Flandre, tableaux de primes) dans le dossier :
`ai_service/documents/`

Puis lancez l'ingestion dans la base vectorielle :
```bash
python ingest.py
```
Les vecteurs créés seront automatiquement sauvegardés dans `ai_service/chroma_db/` !
