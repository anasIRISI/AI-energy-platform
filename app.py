import os
import sys
import requests
import json
import logging
import asyncio
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import chromadb
from local_embeddings import LocalHashEmbeddings

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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_SIMULATION_MODEL = os.getenv("GEMINI_SIMULATION_MODEL", "gemini-3.5-flash-lite")
SIMULATION_WORKER_ENABLED = os.getenv("SIMULATION_WORKER_ENABLED", "true").lower() in {"1", "true", "yes"}
# Une simulation nouvelle est prise en charge rapidement, sans lancer des
# appels IA inutiles en boucle.
SIMULATION_POLL_INTERVAL_SECONDS = max(3, int(os.getenv("SIMULATION_POLL_INTERVAL_SECONDS", "5")))
CHROMA_DIR = "./chroma_db"
WALLONIA_PEB_DATASET_URL = (
    "https://www.odwb.be/api/explore/v2.1/catalog/datasets/"
    "peb-certification-residentielle-batiment-existant/records"
)
logger = logging.getLogger(__name__)
processing_lock = threading.Lock()
worker_status = {"enabled": SIMULATION_WORKER_ENABLED, "lastRunAt": None, "lastResult": None, "running": False}

def get_embeddings():
    """Embeddings locaux déterministes, sans téléchargement ni clé externe."""
    return LocalHashEmbeddings()

def get_vectorstore():
    """Charge la collection Chroma directe, sans LangChain Community."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        return client.get_collection("energieplus_knowledge")
    except Exception as e:
        print(f"[WARN] Impossible de charger ChromaDB : {e}")
    return None

def regional_similarity_search(vectorstore, query: str, region_name: str, k: int = 2):
    """Privilégie les sources explicitement liées à la région de la simulation."""
    canonical_regions = {"bruxelles": "Bruxelles-Capitale"}
    canonical_region = canonical_regions.get(region_name.strip().lower(), region_name)
    result = vectorstore.query(query_embeddings=[get_embeddings().embed_query(query)], n_results=10, where={"region": canonical_region}, include=["documents", "metadatas"])
    candidates = [{"page_content": content, "metadata": metadata or {}} for content, metadata in zip(result.get("documents", [[]])[0], result.get("metadatas", [[]])[0])]
    region_terms = {
        "wallonie": ("wallonie", "wallon"),
        "bruxelles": ("bruxelles", "bruxellois", "renolution"),
        "flandre": ("flandre", "flamand", "vlaanderen", "mijn verbouw"),
    }
    terms = region_terms.get(region_name.strip().lower(), (region_name.strip().lower(),))

    regional_docs = []
    for doc in candidates:
        searchable = f"{doc['metadata'].get('source', '')} {doc['page_content']}".lower()
        if any(term in searchable for term in terms):
            regional_docs.append(doc)

    official = vectorstore.get(
        where={"$and": [{"region": canonical_region}, {"source": "sources_officielles_regionales_2026.txt"}]},
        include=["documents", "metadatas"],
    )
    official_docs = [
        {"page_content": content, "metadata": metadata or {}}
        for content, metadata in zip(official.get("documents", []), official.get("metadatas", []))
    ]
    selected = official_docs + [doc for doc in (regional_docs or candidates) if doc not in official_docs]
    return selected[:k]


def recommendations_from_rag(rag_docs, region_name: str, product_name: str, profil: str) -> tuple[str, list[str]]:
    """Transforme les documents trouvés en conseils traçables et prudents."""
    source_hint = os.path.basename(rag_docs[0]["metadata"].get("source", "source régionale"))
    excerpt = " ".join(rag_docs[0]["page_content"].split())[:360].rstrip(" ,;:")
    return (
        f"Conseils RAG pour {product_name} en {region_name} — source : {source_hint}",
        [
            f"Votre projet concerne {product_name} en {region_name}. Vérifiez d’abord les conditions d’éligibilité correspondant à votre profil {profil}.",
            f"Point extrait de « {source_hint} » : {excerpt}.",
            "Cette estimation est indicative : confirmez les conditions, le budget disponible et les critères techniques sur le portail régional officiel avant de décider.",
        ],
    )


def energy_profile_only(formulaire: dict) -> dict:
    """Ne conserve que les données nécessaires à l'estimation énergétique."""
    answers = formulaire.get("reponses", {}) or {}
    allowed = {
        "surface", "surfaceHabitable", "consommation", "consommationActuelle",
        "orientation", "objectifs", "besoinEnergetique", "typeLogement",
        "chauffage", "tarifMode", "tarifKwh", "niveauIsolation", "anneeBatiment", "scorePebOfficiel",
    }
    return {key: value for key, value in answers.items() if key in allowed}


def _positive_decimal(value: object) -> Optional[Decimal]:
    """Convertit les valeurs saisies côté formulaire sans jamais inventer un tarif."""
    try:
        normalized = str(value).strip().replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace(",", ".")
        parsed = Decimal(normalized)
        return parsed if parsed > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def annual_savings_estimate(formulaire: dict, produit: dict) -> dict[str, Optional[float]]:
    """Fourchette explicite fondée sur le profil, distincte du conseil Gemini.

    Cette règle est volontairement prudente : elle ne prédit ni prime ni prix de
    marché. Les euros ne sont calculés que si le visiteur les a fournis depuis
    sa facture ; sinon le résultat conserve uniquement les kWh/an.
    """
    profile = energy_profile_only(formulaire)
    consumption = _positive_decimal(profile.get("consommation") or profile.get("consommationActuelle"))
    if consumption is None:
        return {"kwh_min": None, "kwh_max": None, "eur_min": None, "eur_max": None, "annual_before": None, "annual_after_min": None, "annual_after_max": None}

    product_type = str(produit.get("type", "")).lower()
    heating = str(profile.get("chauffage", "inconnu")).lower()
    insulation = str(profile.get("niveauIsolation", "inconnu")).lower()
    building_year = str(profile.get("anneeBatiment", "inconnu")).lower()

    if "isolation" in product_type:
        factors = {
            "aucune": (Decimal("0.20"), Decimal("0.30")),
            "faible": (Decimal("0.12"), Decimal("0.20")),
            "recente": (Decimal("0.03"), Decimal("0.07")),
            "inconnu": (Decimal("0.08"), Decimal("0.15")),
        }.get(insulation, (Decimal("0.08"), Decimal("0.15")))
        age_multiplier = {
            "avant_1970": Decimal("1.10"), "1970_1990": Decimal("1.00"),
            "1991_2010": Decimal("0.85"), "apres_2010": Decimal("0.65"), "inconnu": Decimal("0.90"),
        }.get(building_year, Decimal("0.90"))
        heat_share = Decimal("0.70") if heating in {"gaz", "mazout"} else Decimal("0.55") if heating in {"electricite", "pompe_chaleur"} else Decimal("0.60")
        factors = (factors[0] * age_multiplier * heat_share, factors[1] * age_multiplier * heat_share)
    elif "pompe" in product_type or "chaleur" in product_type:
        factors = {
            "mazout": (Decimal("0.20"), Decimal("0.32")), "gaz": (Decimal("0.16"), Decimal("0.27")),
            "electricite": (Decimal("0.08"), Decimal("0.16")), "pompe_chaleur": (Decimal("0.02"), Decimal("0.07")),
            "inconnu": (Decimal("0.10"), Decimal("0.22")),
        }.get(heating, (Decimal("0.10"), Decimal("0.22")))
    elif "panneau" in product_type or "photovolta" in product_type:
        factors = (Decimal("0.20"), Decimal("0.38"))
    elif "batterie" in product_type:
        factors = (Decimal("0.05"), Decimal("0.12"))
    else:
        return {"kwh_min": None, "kwh_max": None, "eur_min": None, "eur_max": None, "annual_before": None, "annual_after_min": None, "annual_after_max": None}

    kwh_min = (consumption * factors[0]).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    kwh_max = (consumption * factors[1]).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    tariff = _positive_decimal(profile.get("tarifKwh")) if profile.get("tarifMode") == "facture" else None
    eur_min = (kwh_min * tariff).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if tariff else None
    eur_max = (kwh_max * tariff).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if tariff else None
    annual_before = (consumption * tariff).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if tariff else None
    annual_after_min = max(Decimal("0"), annual_before - eur_max).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if annual_before is not None and eur_max is not None else None
    annual_after_max = max(Decimal("0"), annual_before - eur_min).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if annual_before is not None and eur_min is not None else None
    return {
        "kwh_min": float(kwh_min), "kwh_max": float(kwh_max),
        "eur_min": float(eur_min) if eur_min is not None else None,
        "eur_max": float(eur_max) if eur_max is not None else None,
        "annual_before": float(annual_before) if annual_before is not None else None,
        "annual_after_min": float(annual_after_min) if annual_after_min is not None else None,
        "annual_after_max": float(annual_after_max) if annual_after_max is not None else None,
    }


def wallonia_peb_comparison(formulaire: dict, region_name: str) -> Optional[str]:
    """Retourne un repère PEB officiel adapté à la Région disponible.

    Le jeu ODWB contient des certificats anonymisés. Quand le visiteur recopie
    son score officiel depuis son certificat, ce score est comparé directement
    au repère régional. Sans score officiel, seule sa consommation déclarée est
    affichée, sans la présenter comme une certification individuelle.
    """
    profile = energy_profile_only(formulaire)
    consumption = _positive_decimal(profile.get("consommation") or profile.get("consommationActuelle"))
    surface = _positive_decimal(profile.get("surface") or profile.get("surfaceHabitable"))
    official_score = _positive_decimal(profile.get("scorePebOfficiel"))
    dwelling = str(profile.get("typeLogement", "")).lower()
    building_period = str(profile.get("anneeBatiment", "")).lower()
    if consumption is None or surface is None or dwelling not in {"maison", "appartement"}:
        return None

    declared_specific = (consumption / surface).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    def visitor_measurement(reference: Decimal, certificate_label: str) -> str:
        if official_score is not None:
            gap = (official_score - reference).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            if gap > 0:
                conclusion = (
                    "Votre logement est moins performant que la moyenne des logements de votre région. "
                    "Cela peut se traduire par davantage de chauffage à payer et un confort moindre en hiver. "
                    "Les travaux proposés dans cette simulation sont une priorité pertinente pour l’améliorer."
                )
            elif gap < 0:
                conclusion = (
                    "Votre logement est plus performant que la moyenne des logements de votre région. "
                    "Les travaux proposés peuvent encore réduire vos dépenses d’énergie et améliorer votre confort."
                )
            else:
                conclusion = (
                    "Votre logement se situe au niveau de la moyenne régionale. "
                    "Les travaux proposés peuvent vous aider à passer à un niveau de confort et d’efficacité supérieur."
                )
            return (
                f"Nous avons utilisé votre certificat {certificate_label} pour comparer votre logement à ceux de votre région. "
                f"{conclusion}"
            )
        return (
            f"Nous avons comparé votre consommation déclarée à celle de logements similaires dans votre région. "
            f"Pour un diagnostic encore plus précis, vous pouvez ajouter la valeur de votre certificat {certificate_label}."
        )
    canonical_region = {"bruxelles": "Bruxelles-Capitale"}.get(region_name.strip().lower(), region_name)
    if canonical_region == "Bruxelles-Capitale":
        reference = Decimal("254")
        return (
            "Comparaison avec des logements certifiés à Bruxelles. "
            f"{visitor_measurement(reference, 'PEB')}"
        )
    if canonical_region == "Flandre":
        average, sample = ((Decimal("397"), "649 041") if dwelling == "maison" else (Decimal("238"), "467 228"))
        return (
            "Comparaison avec des logements certifiés similaires en Flandre. "
            f"{visitor_measurement(average, 'EPC')}"
        )
    if canonical_region != "Wallonie":
        return None

    periods_by_form_value = {
        "avant_1970": ["BEFORE_1919", "BETWEEN_1919_AND_1945", "BETWEEN_1946_AND_1960", "BETWEEN_1961_AND_1970"],
        "1970_1990": ["BETWEEN_1971_AND_1980", "BETWEEN_1981_AND_1985", "BETWEEN_1986_AND_1990"],
        "1991_2010": ["BETWEEN_1991_AND_1995", "BETWEEN_1996_AND_2000", "BETWEEN_2001_AND_2005", "BETWEEN_2006_AND_2010"],
        "apres_2010": ["BETWEEN_2011_AND_2016", "BETWEEN_2017_AND_2020", "BETWEEN_2021_AND_2025"],
    }
    periods = periods_by_form_value.get(building_period)
    if not periods:
        return None

    destination = "SINGLE_FAMILY_HOUSE" if dwelling == "maison" else "APARTMENT"
    quoted_periods = ", ".join(f"'{period}'" for period in periods)
    params = {
        "select": "avg(e_spec) as moyenne, count(*) as total",
        "where": f"destination = '{destination}' AND build_period_v2 IN ({quoted_periods})",
        "limit": 1,
    }
    try:
        response = requests.get(WALLONIA_PEB_DATASET_URL, params=params, timeout=8)
        response.raise_for_status()
        record = (response.json().get("results") or [{}])[0]
        average = _positive_decimal(record.get("moyenne"))
        sample_size = int(record.get("total") or 0)
        if average is None or sample_size <= 0:
            return None
    except (requests.RequestException, ValueError, TypeError, IndexError) as error:
        logger.info("Repère PEB wallon indisponible : %s", type(error).__name__)
        return None

    return (
        "Comparaison avec des logements certifiés similaires en Wallonie. "
        f"{visitor_measurement(average, 'PEB')}"
    )


WALLONIA_PRIME_SOURCE = "https://www.wallonie.be/fr/demarches/obtenir-une-prime-pour-son-habitation-partir-du-14-fevrier-2025"
BRUSSELS_PRIME_SOURCE = "https://environnement.brussels/citoyen/services-et-demandes/primes-et-aides-financieres/les-primes-renolution"
FLANDERS_PRIME_SOURCE = "https://www.vlaanderen.be/bouwen-wonen-en-energie/bouwen-en-verbouwen/premies-voor-renovatie/mijn-verbouwpremie/mijn-verbouwpremie-voor-dak"


def regional_grant_estimate(formulaire: dict, produit: dict, region_name: str) -> dict[str, Optional[object]]:
    """Calcule uniquement une estimation justifiée par un barème officiellement intégré.

    Les données financières précises ne sont pas transmises à Gemini. L'estimation
    est locale et ne constitue jamais une décision d'octroi de la Région.
    """
    answers = formulaire.get("reponses", {}) or {}
    canonical_region = {"bruxelles": "Bruxelles-Capitale"}.get(region_name.strip().lower(), region_name)
    source_by_region = {
        "Wallonie": WALLONIA_PRIME_SOURCE,
        "Bruxelles-Capitale": BRUSSELS_PRIME_SOURCE,
        "Flandre": FLANDERS_PRIME_SOURCE,
    }
    result = {
        "amount": None,
        "status": "Estimation à vérifier sur le portail régional officiel.",
        "source_url": source_by_region.get(canonical_region),
        "note": None,
    }

    if canonical_region == "Bruxelles-Capitale":
        result["status"] = "Le barème RENOLUTION actif n’est pas suffisamment stabilisé pour produire un montant responsable. Vos économies énergie restent calculées ; consultez le portail bruxellois pour l’aide."
        return result
    if canonical_region == "Flandre":
        if "isolation" not in str(produit.get("type", "")).lower():
            result["status"] = "Le barème flamand intégré couvre actuellement l’isolation de toiture."
            return result
        category = str(answers.get("categorieRevenusFlandre", "")).lower()
        quote_htva = _positive_decimal(answers.get("coutTravauxHtva"))
        if category not in {"f3", "f4"} or quote_htva is None:
            result["status"] = "Renseignez la catégorie flamande F3/F4 et le devis HTVA pour calculer l’estimation Mijn VerbouwPremie."
            return result
        rate, ceiling = ((Decimal("0.35"), Decimal("4025")) if category == "f3" else (Decimal("0.50"), Decimal("5750")))
        eligible_cost = min(quote_htva, Decimal("11500"))
        amount = min(eligible_cost * rate, ceiling).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.update({
            "amount": float(amount),
            "status": "Estimation Flandre 2026 : Mijn VerbouwPremie pour isolation de toiture, à confirmer lors de la demande.",
            "note": "Calcul : pourcentage de la facture HTVA, plafonné selon la catégorie flamande F3/F4 et le plafond de facture admissible.",
        })
        return result
    if canonical_region != "Wallonie":
        result["status"] = "Aucun barème régional intégré pour cette situation."
        return result
    if "isolation" not in str(produit.get("type", "")).lower():
        result["status"] = "Le barème local intégré couvre actuellement l’isolation de toiture en Wallonie."
        return result

    required = {
        "surfaceTravauxM2": _positive_decimal(answers.get("surfaceTravauxM2")),
        "coutTravauxTtc": _positive_decimal(answers.get("coutTravauxTtc")),
        "anneeConstruction": _positive_decimal(answers.get("anneeConstruction")),
        "categorieRevenus": answers.get("categorieRevenus"),
        "statutDemandeur": answers.get("statutDemandeur"),
        "entrepreneurEnregistre": answers.get("entrepreneurEnregistre"),
    }
    missing = [key for key, value in required.items() if value in (None, "", "inconnu")]
    if missing:
        result["status"] = "Renseignez le profil prime (année, surface à isoler, devis TTC, catégorie de revenus, statut et entrepreneur) pour obtenir une estimation wallonne."
        return result

    if required["anneeConstruction"] > Decimal("2011"):
        result["status"] = "Selon l’année indiquée, le logement ne satisfait pas encore au critère wallon de 15 ans. Vérifiez la date du permis."
        return result
    if required["statutDemandeur"] not in {"proprietaire", "usufruitier", "copropriete"}:
        result["status"] = "Le statut renseigné ne permet pas de confirmer le droit réel requis. Vérifiez votre situation sur le portail wallon."
        return result
    if required["entrepreneurEnregistre"] != "oui":
        result["status"] = "L’estimation nécessite des travaux réalisés par un entrepreneur enregistré."
        return result

    multiplier = {"r1": Decimal("6"), "r2": Decimal("4"), "r3": Decimal("3"), "r4": Decimal("2")}.get(str(required["categorieRevenus"]).lower())
    if multiplier is None:
        result["status"] = "Choisissez une catégorie de revenus wallonne R1 à R4 pour calculer la prime."
        return result
    base_per_m2 = Decimal("26") if answers.get("isolantBiosource") == "oui" else Decimal("20")
    work_cost = required["coutTravauxTtc"]
    if work_cost is None:
        result["status"] = "Le montant TTC du devis est nécessaire pour appliquer le plafond réglementaire."
        return result
    cap_rate = Decimal("0.70") if str(required["categorieRevenus"]).lower() in {"r1", "r2"} else Decimal("0.50")
    estimated = min(base_per_m2 * required["surfaceTravauxM2"] * multiplier, work_cost * cap_rate)
    amount = estimated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result.update({
        "amount": float(amount),
        "status": "Estimation Wallonie 2025–2026 : montant à confirmer lors de la demande officielle.",
        "note": "Calcul : barème isolation toiture × catégorie de revenus, plafonné au devis TTC déclaré. Les conditions techniques et administratives restent à vérifier.",
    })
    return result


def gemini_simulation_advice(produit: dict, region_name: str, formulaire: dict, rag_docs: list[dict], peb_comparison: Optional[str]) -> tuple[float, str, list[str]]:
    """Gemini génère une analyse avec RAG si disponible, sinon une estimation technique prudente."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY est absente : la simulation Gemini ne peut pas être exécutée.")
    sources = [{"source": doc["metadata"].get("source", "source régionale"), "extrait": " ".join(doc["page_content"].split())[:700]} for doc in rag_docs[:2]]
    prompt = {
        "role": "Tu es un conseiller énergie belge. Réponds uniquement en français.",
        "task": "Produis une analyse indicative fondée sur les données du projet et, si elles existent, les sources régionales fournies.",
        "product": {"nom": produit.get("nom"), "type": produit.get("type"), "prixCatalogue": produit.get("prix")},
        "region": region_name,
        "profilEnergie": energy_profile_only(formulaire),
        "comparaisonPEBPublique": peb_comparison,
        "sourcesRAG": sources,
        "constraints": ["Ne prétends jamais qu'une prime est accordée.", "Ne transforme jamais une consommation déclarée en certificat PEB individuel.", "S'il n'y a pas de source régionale, n'affirme aucune règle, obligation ou prime régionale.", "Ne donne aucun montant de prime non présent dans les sources.", "N'inclus aucune information de contact ou donnée personnelle.", "Chaque conseil doit être directement lié à au moins un champ reçu : chauffage, isolation, année du bâtiment, consommation, surface ou objectif du visiteur.", "Donne exactement 3 conseils brefs, actionnables et non redondants.", "Réponds strictement avec du JSON : scoreValeur (nombre entre 0 et 10), resume (texte court), recommandations (tableau de 3 conseils concrets)."],
    }
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_SIMULATION_MODEL}:generateContent",
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700, "responseMimeType": "application/json"}},
            timeout=45,
        )
        if not response.ok:
            raise ValueError(f"Gemini a retourné le statut HTTP {response.status_code}.")
        raw = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        parsed = json.loads(raw.removeprefix("```json").removesuffix("```").strip())
        score = float(parsed["scoreValeur"])
        recommendations = [str(item).strip() for item in parsed["recommandations"] if str(item).strip()][:3]
        if not 0 <= score <= 10 or len(recommendations) < 3:
            raise ValueError("La réponse Gemini ne respecte pas le contrat de simulation.")
        source_label = os.path.basename(sources[0]["source"]) if sources else "données du formulaire et catalogue"
        method_label = "Analyse Gemini fondée sur RAG" if sources else "Analyse Gemini indicative, sans source régionale"
        summary = str(parsed.get("resume", "")).strip()
        criteria = f"{method_label} — source : {source_label}"
        return score, f"{criteria}. {summary}".strip(), recommendations
    except Exception as error:
        logger.warning("Simulation Gemini indisponible : %s", type(error).__name__)
        raise RuntimeError("Gemini n'a pas pu produire une analyse fiable. La simulation reste en attente ; réessayez plus tard.") from error

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
        "embedding_engine": os.getenv("EMBEDDING_PROVIDER", "huggingface (local)"),
        "simulation_provider": "gemini" if GEMINI_API_KEY else "not_configured",
        "simulation_model": GEMINI_SIMULATION_MODEL if GEMINI_API_KEY else None,
        "simulation_worker": worker_status,
    }


@app.get("/worker-status")
def get_worker_status():
    """État lisible du worker automatique de simulations."""
    return worker_status

@app.post("/query-rag")
def query_rag(req: QuestionRequest):
    """Interroge la base de connaissances RAG sur les primes, le PEB ou les produits."""
    vs = get_vectorstore()
    if not vs:
        return {"error": "Base vectorielle non initialisée. Exécutez 'python ingest.py' d'abord."}
    
    if req.region and req.region != "Belgique":
        documents = regional_similarity_search(vs, req.query, req.region, k=3)
        snippets = [{"source": doc["metadata"].get("source", "doc"), "content": doc["page_content"][:300]} for doc in documents]
    else:
        result = vs.query(query_embeddings=[get_embeddings().embed_query(req.query)], n_results=3, include=["documents", "metadatas"])
        snippets = [{"source": metadata.get("source", "doc"), "content": content[:300]} for content, metadata in zip(result.get("documents", [[]])[0], result.get("metadatas", [[]])[0])]
    return {
        "query": req.query,
        "total_sources": len(snippets),
        "results": snippets
    }

@app.post("/process-pending-simulations")
def process_pending_simulations():
    """Récupère et calcule automatiquement toutes les simulations en attente côté Spring Boot avec le RAG."""
    if not processing_lock.acquire(blocking=False):
        return {"status": "RUNNING", "simulations_traitees": [], "message": "Un traitement est déjà en cours."}
    headers = {"X-API-KEY": AI_API_KEY}
    vs = get_vectorstore()
    worker_status["running"] = True
    worker_status["lastRunAt"] = datetime.now(timezone.utc).isoformat()
    
    try:
        resp = requests.get(f"{SPRING_BOOT_URL}/api/ai/simulations/en-attente", headers=headers, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        
        pending_simulations = resp.json()
        processed_results = []
        failures = []

        for sim in pending_simulations:
            sim_id = sim.get("id")
            try:
                ctx_resp = requests.get(f"{SPRING_BOOT_URL}/api/ai/simulations/{sim_id}/contexte", headers=headers, timeout=15)
                ctx_resp.raise_for_status()
                ctx = ctx_resp.json()
                formulaire = ctx.get("formulaire", {})
                produit = ctx.get("produit", {})
                regions = ctx.get("regions", [])
                region_name = regions[0]['nom'] if regions else 'Belgique'
                rag_docs = regional_similarity_search(vs, f"primes {region_name} {produit.get('nom', '')} {formulaire.get('profil', '')}", region_name, k=2) if vs else []
                if not rag_docs:
                    logger.info("Aucune source RAG pour %s : estimation technique prudente utilisée.", region_name)
                peb_comparison = wallonia_peb_comparison(formulaire, region_name)
                score_val, criteres_label, gemini_recommendations = gemini_simulation_advice(
                    produit, region_name, formulaire, rag_docs, peb_comparison
                )
                savings = annual_savings_estimate(formulaire, produit)
                grant = regional_grant_estimate(formulaire, produit, region_name)
                declared_quote = _positive_decimal((formulaire.get("reponses", {}) or {}).get("coutTravauxTtc"))
                # Quatre cartes maximum : le repère de données, puis trois
                # actions Gemini. Les économies et primes ont leur propre zone
                # dans le résultat, elles ne doivent pas encombrer les conseils.
                recommandations = ([peb_comparison] if peb_comparison else []) + gemini_recommendations
                recommandations = recommandations[:4]
                result_payload = {
                    "coutEstime": float(declared_quote) if declared_quote else produit.get("prix", 6500.0),
                    "primeEstimee": grant["amount"], "primeStatut": grant["status"], "primeSourceUrl": grant["source_url"],
                    "economiesAnnuellesMin": savings["eur_min"], "economiesAnnuellesMax": savings["eur_max"],
                    "coutEnergieAnnuelAvant": savings["annual_before"],
                    "coutEnergieAnnuelApresMin": savings["annual_after_min"], "coutEnergieAnnuelApresMax": savings["annual_after_max"],
                    "economiesEnergieMinKwh": savings["kwh_min"], "economiesEnergieMaxKwh": savings["kwh_max"],
                    "scoreValeur": score_val, "scoreCriteres": criteres_label,
                    "recommandations": recommandations,
                }
                post_resp = requests.post(f"{SPRING_BOOT_URL}/api/ai/simulations/{sim_id}/resultat", json=result_payload, headers=headers, timeout=20)
                post_resp.raise_for_status()
                processed_results.append(sim_id)
            except Exception as error:
                logger.warning("Simulation %s non traitée : %s", sim_id, error)
                failures.append({"id": sim_id, "error": "La simulation sera réessayée automatiquement."})

        result = {"status": "SUCCESS" if not failures else "PARTIAL", "simulations_traitees": processed_results, "simulations_en_echec": failures}
        worker_status["lastResult"] = result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        worker_status["running"] = False
        processing_lock.release()


async def simulation_worker_loop():
    """Traite automatiquement les demandes créées par le bouton Simuler."""
    await asyncio.sleep(3)
    while True:
        try:
            await asyncio.to_thread(process_pending_simulations)
        except Exception as error:
            logger.warning("Worker automatique indisponible : %s", type(error).__name__)
        await asyncio.sleep(SIMULATION_POLL_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_simulation_worker():
    if SIMULATION_WORKER_ENABLED:
        app.state.simulation_worker_task = asyncio.create_task(simulation_worker_loop())


@app.on_event("shutdown")
async def stop_simulation_worker():
    task = getattr(app.state, "simulation_worker_task", None)
    if task:
        task.cancel()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    print(f"[AI_SERVICE] Démarrage du serveur FastAPI RAG sur http://127.0.0.1:{port} ...")
    uvicorn.run(app, host="127.0.0.1", port=port)

