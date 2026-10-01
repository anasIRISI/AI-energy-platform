from __future__ import annotations

import shutil
import sys
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


INPUT = Path(r"C:\Users\hp\Downloads\Rapport_PFA_EcoReno_Final_IA_Detaillee.docx")
OUTPUT = Path(r"C:\Users\hp\Documents\AI-energy-platform\Rapport_PFA_EcoReno_Impression.docx")


def set_font(run, size: float, bold: bool) -> None:
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), "Times New Roman")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = False
    run.font.color.rgb = RGBColor(0, 0, 0)


def set_style(document: Document, name: str, size: float, bold: bool, before: float, after: float) -> None:
    try:
        style = document.styles[name]
    except KeyError:
        style = document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    style.font.name = "Times New Roman"
    rpr = style._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Times New Roman")
    rfonts.set(qn("w:hAnsi"), "Times New Roman")
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_before = Pt(before)
    style.paragraph_format.space_after = Pt(after)


def clean_heading(text: str) -> str:
    return " ".join(text.replace("\u00a0", " ").split()).rstrip(":")


def set_heading(paragraph, style_name: str) -> None:
    paragraph.style = style_name
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if style_name == "Heading 1" else WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.keep_together = True
    if style_name == "Heading 1":
        paragraph.paragraph_format.page_break_before = True
    paragraph.text = clean_heading(paragraph.text)
    size = {"Heading 1": 16, "Heading 2": 14, "Heading 3": 13, "Heading 4": 12}[style_name]
    for run in paragraph.runs:
        set_font(run, size, True)


def set_update_fields(document: Document) -> None:
    settings = document.settings.element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")

    for instr in document._element.iter(qn("w:instrText")):
        if "TOC \\o \"1-3\"" in (instr.text or ""):
            instr.text = instr.text.replace('TOC \\o "1-3"', 'TOC \\o "1-4"')
    for field_char in document._element.iter(qn("w:fldChar")):
        if field_char.get(qn("w:fldCharType")) == "begin":
            field_char.set(qn("w:dirty"), "true")


def replace_paragraph_text(paragraph, value: str) -> None:
    paragraph.text = value
    for run in paragraph.runs:
        set_font(run, 12, False)


def remove_paragraph(paragraph) -> None:
    paragraph._element.getparent().remove(paragraph._element)


def find_paragraph(document: Document, text: str):
    for paragraph in document.paragraphs:
        if clean_heading(paragraph.text) == text:
            return paragraph
    return None


def main() -> None:
    shutil.copy2(INPUT, OUTPUT)
    document = Document(OUTPUT)

    # Normalise the core report typography without changing the cover page.
    set_style(document, "Normal", 12, False, 0, 6)
    set_style(document, "Heading 1", 16, True, 18, 12)
    set_style(document, "Heading 2", 14, True, 14, 8)
    set_style(document, "Heading 3", 13, True, 10, 6)
    set_style(document, "Heading 4", 12, True, 8, 4)
    set_style(document, "TOC Heading", 14, True, 12, 8)

    # Establish the actual heading hierarchy used by the report.
    heading_map = {
        "Heading 1": [19, 29, 137, 154, 189, 300, 430, 454],
        "Heading 2": [145, 155, 157, 162, 167, 176, 182, 190, 194, 209, 227, 239, 244, 250, 295, 301, 303, 326, 337, 345, 350, 356, 359, 363],
        "Heading 3": [251, 255, 260, 265, 268, 272, 277, 280, 284, 307, 311, 315, 318, 322, 327, 364, 367, 372, 390, 415, 418],
        "Heading 4": [373, 378, 382, 387, 391, 396, 401, 404],
    }
    for style_name, indexes in heading_map.items():
        for index in indexes:
            if index < len(document.paragraphs):
                set_heading(document.paragraphs[index], style_name)

    # Correct small naming errors and remove unsupported AI wording.
    replacements = {
        173: "Développer un service de simulation énergétique capable d'analyser les données fournies par l'utilisateur et d'estimer les économies et performances potentielles d'une installation.",
        179: "La deuxième fonctionnalité est un service de simulation énergétique hybride. Il exploite les données fournies par l'utilisateur, des règles de calcul explicites et des paramètres régionaux afin de produire des estimations personnalisées et des recommandations adaptées.",
        247: "Le module IA intègre deux fonctionnalités principales : un assistant intelligent basé sur le RAG pour répondre aux questions des utilisateurs et un service de simulation énergétique hybride pour produire des estimations explicables.",
        255: "7.2 Spring Boot",
        260: "7.3 PostgreSQL",
        265: "7.4 DBeaver",
        266: "DBeaver est un outil graphique de gestion de bases de données. Dans le cadre du projet EcoReno+, il est utilisé pour administrer et consulter la base de données PostgreSQL utilisée par le backend Spring Boot.",
        271: "Dans ce projet, Python est utilisé pour les fonctionnalités liées à l'intelligence artificielle et au traitement de la simulation énergétique. Son écosystème de bibliothèques permet de développer et d'intégrer les traitements nécessaires à l'analyse des données.",
        272: "7.6 FastAPI",
        277: "7.7 API REST",
        280: "7.8 Git",
        296: "L'architecture mise en place sépare les responsabilités de l'application. React assure l'interface utilisateur, Spring Boot prend en charge la logique métier et PostgreSQL la persistance des données. Les fonctionnalités d'intelligence artificielle sont regroupées dans un microservice Python utilisant FastAPI, avec un assistant RAG et un service de simulation énergétique hybride. Cette organisation facilite l'intégration et l'évolution des composants de la solution.",
        337: "3.2 Dashboard administrateur",
        345: "3.3 Interface de simulation énergétique",
        350: "3.4 Interface du chatbot intelligent",
        356: "3.5 Communication avec le backend",
        359: "3.6 Résultats de la réalisation du frontend",
        366: "Cette partie s'appuie sur les services présents dans le projet. Le chatbot est développé dans un microservice FastAPI distinct et s'appuie sur un modèle Gemini Flash. Le service IA de simulation et de recherche RAG expose notamment la route POST /query-rag et communique avec Spring Boot pour traiter les simulations.",
        388: "Le chatbot utilise un modèle Gemini Flash afin de produire des réponses courtes et compréhensibles en français, encadrées par les extraits RAG et les règles métier du projet. La génération est volontairement limitée : le chatbot ne doit pas annoncer une aide, un prix ou une économie chiffrée sans source appropriée.",
        422: "Le module IA d'EcoReno+ repose ainsi sur des éléments implémentés : chatbot Luna connecté au backend, modèle Gemini Flash encadré par des règles métier, RAG sur ChromaDB, corpus documentaire local et simulation hybride explicable. L'évolution la plus pertinente consiste à enrichir le corpus documentaire et à constituer un jeu de données de référence pour comparer, avec de vraies métriques, des modèles prédictifs de consommation ou d'économies.",
    }
    for index, value in replacements.items():
        if index < len(document.paragraphs):
            replace_paragraph_text(document.paragraphs[index], value)

    # Restore heading formatting after textual corrections.
    for style_name, indexes in heading_map.items():
        for index in indexes:
            if index < len(document.paragraphs):
                set_heading(document.paragraphs[index], style_name)

    # Titles for navigational lists stay out of the main TOC.
    for index in [37, 93, 124]:
        paragraph = document.paragraphs[index]
        paragraph.style = "TOC Heading"
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.keep_with_next = True
        for run in paragraph.runs:
            set_font(run, 14, True)

    # Repair a few inherited heading styles that used inconsistent colours.
    for text, style_name in {
        "7.10 Environnement de développement et autres outils": "Heading 3",
        "Synthèse de l’architecture": "Heading 2",
        "Conclusion générale": "Heading 2",
        "Limites du projet": "Heading 2",
    }.items():
        paragraph = find_paragraph(document, text)
        if paragraph is not None:
            set_heading(paragraph, style_name)

    # Remove empty paragraphs that created a blank page before the final chapter.
    conclusion = find_paragraph(document, "Conclusion générale et perspectives")
    if conclusion is not None:
        previous = conclusion._element.getprevious()
        while previous is not None and not previous.xpath(".//w:t[normalize-space()]"):
            earlier = previous.getprevious()
            previous.getparent().remove(previous)
            previous = earlier

    # The chapter title announces perspectives: add this missing academic subsection,
    # then retain the bibliography on its own final page.
    bibliography = find_paragraph(document, "Bibliographie et webographie")
    if bibliography is not None and find_paragraph(document, "Perspectives du projet") is None:
        perspective_title = bibliography.insert_paragraph_before("Perspectives du projet")
        set_heading(perspective_title, "Heading 2")
        for text_value in [
            "Les perspectives d'évolution du projet concernent d'abord l'enrichissement continu de la base de connaissances du chatbot avec des documents officiels, des guides techniques et des informations régionales mises à jour. Cette évolution renforcerait la pertinence des réponses tout en conservant leur traçabilité.",
            "La simulation pourra également être améliorée par la constitution d'un jeu de données de référence, permettant de comparer de manière rigoureuse des modèles prédictifs avec des indicateurs réels tels que la MAE, la RMSE ou le coefficient R². Les règles métier actuelles resteraient alors un socle explicable et contrôlable.",
            "L'intégration de données météorologiques, de tarifs énergétiques et de règles de primes actualisées rendrait les recommandations plus précises. Une version mobile, des tableaux de bord CRM enrichis et une exportation native au format .xlsx constituent également des évolutions fonctionnelles pertinentes.",
            "Enfin, un déploiement sur une infrastructure cloud sécurisée permettrait d'améliorer la disponibilité de la plateforme, tout en protégeant les données, les clés d'API et les échanges entre les différents services.",
        ]:
            paragraph = bibliography.insert_paragraph_before(text_value)
            paragraph.style = "Normal"
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.line_spacing = 1.5
            paragraph.paragraph_format.space_after = Pt(6)
            for run in paragraph.runs:
                set_font(run, 12, False)

    # Improve the alignment of report body paragraphs and captions.
    excluded_styles = {"TOC 1", "TOC 2", "TOC 3", "TOC 4", "table of figures", "Caption", "Caption1", "TOC Heading"}
    for index, paragraph in enumerate(document.paragraphs):
        # The first 137 paragraphs contain the cover and front matter; preserve their layout.
        if index >= 137 and paragraph.style.name == "Normal" and paragraph.text.strip():
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.line_spacing = 1.5
        if paragraph.style.name in {"Caption", "Caption1"}:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.keep_with_next = True
            for run in paragraph.runs:
                set_font(run, 11, False)

    set_update_fields(document)
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
