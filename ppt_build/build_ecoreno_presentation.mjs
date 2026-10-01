import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const SKILL_DIR = "C:\\Users\\hp\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.915.20218\\skills\\presentations";
const workspaceDir = "C:\\Users\\hp\\Documents\\AI-energy-platform";
const buildDir = path.join(workspaceDir, "ppt_build");
const outputDir = path.join(workspaceDir, "presentations");
const finalPath = path.join(outputDir, "Presentation_EcoReno_PFA_10min.pptx");
const assetDir = path.join(workspaceDir, "ppt_assets", "word", "media");
const RUNTIME_PYTHON = "C:\\Users\\hp\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";

const { resolvePresentationFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools", "artifact_tool_utils.mjs")).href,
);

await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });
const font = resolvePresentationFont({ fontFamily: "Aptos" });
const ppt = Presentation.create({ slideSize: { width: 1280, height: 720 } });

const C = { navy: "#073B4C", blue: "#1F7AE0", teal: "#138C86", green: "#2F9E62", pale: "#F4FAF8", mint: "#E6F5EF", sky: "#EAF5FF", ink: "#17212B", muted: "#58707A", gold: "#F5B700", white: "#FFFFFF", line: "#CBE3DA" };

function addText(slide, text, left, top, width, height, size = 22, opts = {}) {
  const shape = slide.shapes.add({ geometry: "textbox", position: { left, top, width, height }, fill: "none", line: { fill: "none", width: 0 } });
  shape.text = text;
  shape.text.style = { typeface: font, fontSize: size, color: opts.color ?? C.ink, bold: opts.bold ?? false, italic: opts.italic ?? false, autoFit: "shrinkText", paragraphSpacing: 6, marginLeft: 0, marginRight: 0, marginTop: 0, marginBottom: 0, align: opts.align ?? "left" };
  return shape;
}

function rect(slide, left, top, width, height, fill, radius = "rounded-xl", line = "none") {
  return slide.shapes.add({ geometry: "roundRect", position: { left, top, width, height }, fill: { color: fill }, line: line === "none" ? { fill: "none", width: 0 } : { fill: line, width: 1 } });
}

async function img(slide, name, left, top, width, height, alt, fit = "contain") {
  const blob = await fs.readFile(path.join(assetDir, name));
  slide.images.add({ blob, contentType: name.endsWith("jpeg") ? "image/jpeg" : "image/png", alt, fit, geometry: "roundRect", borderRadius: "rounded-xl", position: { left, top, width, height } });
}

function base(slide, section, n) {
  slide.background.fill = C.white;
  slide.shapes.add({ geometry: "rect", position: { left: 0, top: 0, width: 1280, height: 16 }, fill: { color: C.teal }, line: { fill: "none", width: 0 } });
  addText(slide, "EcoReno+  |  Projet de fin d'année", 64, 678, 440, 20, 12, { color: C.muted });
  addText(slide, section, 875, 678, 265, 20, 12, { color: C.muted, align: "right" });
  addText(slide, String(n).padStart(2, "0"), 1155, 678, 55, 20, 12, { color: C.teal, bold: true, align: "right" });
}

function title(slide, text, sub) {
  addText(slide, text, 72, 58, 850, 50, 32, { color: C.navy, bold: true });
  if (sub) addText(slide, sub, 72, 112, 800, 34, 16, { color: C.muted });
}

function bullet(slide, text, left, top, width, color = C.ink) {
  addText(slide, "•", left, top - 1, 20, 28, 22, { color: C.green, bold: true });
  addText(slide, text, left + 24, top, width - 24, 45, 18, { color });
}

// 1. Cover
{
  const s = ppt.slides.add();
  s.background.fill = C.pale;
  s.shapes.add({ geometry: "rect", position: { left: 0, top: 0, width: 1280, height: 720 }, fill: { color: C.pale }, line: { fill: "none", width: 0 } });
  s.shapes.add({ geometry: "ellipse", position: { left: 830, top: -170, width: 560, height: 560 }, fill: { color: C.mint }, line: { fill: "none", width: 0 } });
  s.shapes.add({ geometry: "ellipse", position: { left: 945, top: 350, width: 430, height: 430 }, fill: { color: C.sky }, line: { fill: "none", width: 0 } });
  await img(s, "image21.png", 710, 92, 500, 420, "Interface EcoReno+", "cover");
  rect(s, 72, 94, 110, 8, C.green, "rounded-sm");
  addText(s, "EcoReno+", 72, 135, 500, 64, 48, { color: C.navy, bold: true });
  addText(s, "Plateforme intelligente d'accompagnement à la rénovation énergétique", 72, 210, 560, 105, 31, { color: C.teal, bold: true });
  addText(s, "Projet de fin d'année en Génie Informatique\nHajar El Khatib  |  ENSI Tanger  |  2026", 72, 350, 520, 74, 18, { color: C.muted });
  addText(s, "Durée de présentation : 10 minutes", 72, 560, 330, 28, 16, { color: C.green, bold: true });
  s.speakerNotes.textFrame.setText("Bonjour. Je vais présenter EcoReno+, une plateforme qui accompagne les utilisateurs dans un projet de rénovation énergétique, depuis l'information jusqu'à la simulation et au rendez-vous.");
}

// 2. Problem
{
  const s = ppt.slides.add(); base(s, "Contexte", 2); title(s, "Problématique", "Un parcours énergétique reste difficile à comprendre et à personnaliser");
  rect(s, 72, 185, 530, 370, C.sky); rect(s, 660, 185, 545, 370, C.mint);
  addText(s, "Pour le visiteur", 110, 220, 260, 28, 22, { color: C.navy, bold: true });
  bullet(s, "Informations techniques dispersées", 112, 274, 410);
  bullet(s, "Difficulté à choisir une solution adaptée", 112, 338, 430);
  bullet(s, "Estimation des économies peu accessible", 112, 402, 420);
  addText(s, "Pour l'administrateur", 700, 220, 310, 28, 22, { color: C.navy, bold: true });
  bullet(s, "Suivi manuel des demandes et rendez-vous", 702, 274, 425);
  bullet(s, "Besoin de centraliser les données CRM", 702, 338, 425);
  bullet(s, "Besoin d'un outil de conseil cohérent", 702, 402, 425);
  addText(s, "Question centrale : comment guider l'utilisateur vers une décision énergétique plus claire, tout en donnant à l'administration une vision complète des demandes ?", 90, 590, 1080, 46, 21, { color: C.teal, bold: true, align: "center" });
  s.speakerNotes.textFrame.setText("Le problème porte autant sur l'expérience du visiteur que sur le suivi administratif. Les informations sur les solutions, les primes et les performances sont nombreuses. Il faut donc simplifier le parcours tout en gardant une gestion fiable des données.");
}

// 3 Solution
{
  const s = ppt.slides.add(); base(s, "Solution proposée", 3); title(s, "Solution proposée", "Une plateforme web qui relie information, simulation et accompagnement");
  await img(s, "image23.png", 722, 165, 432, 460, "Solutions énergétiques EcoReno+", "contain");
  const items = [["Catalogue", "Solutions énergétiques et informations régionales"], ["Simulation", "Estimation personnalisée avec score, économies et recommandations"], ["Luna", "Assistant conversationnel pour guider l'utilisateur"], ["CRM", "Suivi des formulaires, produits et rendez-vous"]];
  let y = 185;
  for (const [h, b] of items) { rect(s, 80, y, 560, 82, C.pale, "rounded-xl", C.line); addText(s, h, 108, y + 17, 180, 26, 21, { color: C.navy, bold: true }); addText(s, b, 108, y + 45, 480, 25, 15, { color: C.muted }); y += 94; }
  s.speakerNotes.textFrame.setText("EcoReno+ propose un seul parcours. L'utilisateur commence par découvrir les solutions, remplit un formulaire, obtient une simulation et peut demander un rendez-vous. L'administrateur suit ces informations depuis l'espace CRM.");
}

// 4 Conception
{
  const s = ppt.slides.add(); base(s, "Conception", 4); title(s, "Conception fonctionnelle", "Les acteurs et les cas d'utilisation ont guidé la réalisation");
  await img(s, "image3.png", 80, 160, 650, 450, "Diagramme de cas d'utilisation EcoReno+", "contain");
  addText(s, "Acteurs", 790, 180, 250, 28, 24, { color: C.navy, bold: true });
  bullet(s, "Visiteur particulier", 790, 230, 340);
  bullet(s, "Entreprise ou société", 790, 284, 340);
  bullet(s, "Administrateur", 790, 338, 340);
  addText(s, "Fonctionnalités clés", 790, 420, 280, 28, 24, { color: C.navy, bold: true });
  bullet(s, "Simuler un projet", 790, 470, 340);
  bullet(s, "Échanger avec Luna", 790, 524, 340);
  bullet(s, "Gérer les demandes", 790, 578, 340);
  s.speakerNotes.textFrame.setText("La conception a commencé par les acteurs. Le visiteur consulte le catalogue, remplit un formulaire, lance une simulation et échange avec Luna. L'administrateur supervise ensuite les données et les rendez-vous.");
}

// 5 Architecture
{
  const s = ppt.slides.add(); base(s, "Architecture", 5); title(s, "Architecture technique", "Des services séparés pour garder une application évolutive");
  await img(s, "image5.png", 92, 155, 1095, 490, "Architecture React Spring Boot PostgreSQL FastAPI", "contain");
  addText(s, "React affiche l'expérience utilisateur. Spring Boot centralise la logique métier. PostgreSQL conserve les données. FastAPI exécute les services IA.", 110, 625, 1060, 28, 17, { color: C.teal, bold: true, align: "center" });
  s.speakerNotes.textFrame.setText("Cette architecture sépare clairement les responsabilités. Le frontend React assure l'interface. Spring Boot gère les règles métier et les API. PostgreSQL assure la persistance. FastAPI porte les services IA, le RAG et le worker de simulation.");
}

// 6 Technologies
{
  const s = ppt.slides.add(); base(s, "Technologies", 6); title(s, "Technologies utilisées", "Une stack adaptée à une plateforme web et à des services IA");
  const tech = [["React", "Interface web"], ["Spring Boot", "API REST et logique métier"], ["PostgreSQL", "Données et historique"], ["FastAPI", "Services IA et worker"], ["ChromaDB", "Recherche documentaire RAG"], ["Gemini", "Conseils génératifs encadrés"]];
  let x = 80, y = 185;
  tech.forEach((t, i) => { rect(s, x, y, 330, 125, i % 2 === 0 ? C.sky : C.mint); addText(s, t[0], x + 24, y + 27, 260, 30, 24, { color: C.navy, bold: true }); addText(s, t[1], x + 24, y + 69, 270, 34, 16, { color: C.muted }); x += 370; if (x > 800) { x = 80; y += 155; } });
  addText(s, "Les échanges entre les composants utilisent des API REST et des données JSON.", 84, 560, 1020, 32, 20, { color: C.teal, bold: true });
  s.speakerNotes.textFrame.setText("Les technologies correspondent aux responsabilités. React sert l'interface, Spring Boot les opérations métier, PostgreSQL les données, et FastAPI les traitements IA. ChromaDB prend en charge la recherche documentaire, et Gemini apporte des explications adaptées au contexte.");
}

// 7 Backend
{
  const s = ppt.slides.add(); base(s, "Réalisation", 7); title(s, "Réalisation du backend", "Le backend centralise le métier, les données et la sécurité");
  const steps = [["API REST", "Contrôleurs pour les opérations de l'application"], ["Services métier", "Simulation, chatbot, rendez-vous, catalogue et CRM"], ["Persistance", "Entités JPA et repositories PostgreSQL"], ["Sécurité", "Accès administrateur protégé par authentification"]];
  let y = 188;
  for (const [h, b] of steps) { rect(s, 75, y, 535, 76, C.pale, "rounded-xl", C.line); addText(s, h, 106, y + 13, 180, 24, 20, { color: C.navy, bold: true }); addText(s, b, 106, y + 41, 440, 25, 15, { color: C.muted }); y += 91; }
  await img(s, "image21.png", 670, 185, 465, 300, "Page d'accueil de l'application", "cover");
  addText(s, "Le backend conserve les formulaires, résultats de simulation, conversations et rendez-vous pour un suivi cohérent dans le CRM.", 670, 515, 470, 70, 19, { color: C.teal, bold: true });
  s.speakerNotes.textFrame.setText("Le backend représente le cœur de l'application. Il expose les API REST, applique les règles métier et conserve l'historique. Il assure également la protection de l'espace administrateur.");
}

// 8 Simulation
{
  const s = ppt.slides.add(); base(s, "Intelligence artificielle", 8); title(s, "Simulation énergétique", "Un traitement asynchrone qui produit un résultat enregistré");
  await img(s, "image29.png", 720, 150, 480, 450, "Résultat d'une simulation EcoReno+", "contain");
  const flow = ["Formulaire", "Simulation en attente", "Worker FastAPI", "Calcul et recommandations", "Résultat affiché"];
  let y = 175;
  flow.forEach((label, i) => { rect(s, 85, y, 490, 56, i === 2 ? C.mint : C.sky); addText(s, label, 115, y + 14, 410, 25, 20, { color: C.navy, bold: true, align: "center" }); if (i < flow.length - 1) addText(s, "↓", 312, y + 56, 36, 28, 24, { color: C.green, bold: true, align: "center" }); y += 83; });
  addText(s, "Le résultat présente un score énergétique, une estimation et des recommandations associées au projet de l'utilisateur.", 85, 610, 510, 45, 17, { color: C.muted });
  s.speakerNotes.textFrame.setText("La simulation démarre avec le formulaire. Spring Boot enregistre la demande. Le worker FastAPI récupère le contexte, applique les règles de calcul, ajoute si possible un conseil génératif, puis renvoie le résultat au backend. Le frontend affiche ensuite les résultats sauvegardés.");
}

// 9 Luna
{
  const s = ppt.slides.add(); base(s, "Intelligence artificielle", 9); title(s, "Chatbot Luna et recherche RAG", "Un assistant qui combine conversation et connaissances du projet");
  await img(s, "image31.png", 680, 155, 510, 440, "Interface du chatbot Luna", "contain");
  addText(s, "Parcours d'une question", 90, 185, 380, 28, 23, { color: C.navy, bold: true });
  const rag = [["Question utilisateur", C.sky], ["Recherche dans ChromaDB", C.mint], ["Extraits documentaires régionaux", "#FFF4D6"], ["Réponse de Luna avec Gemini", C.sky]];
  let y = 235;
  rag.forEach(([label, fill], i) => { rect(s, 92, y, 455, 54, fill); addText(s, label, 118, y + 14, 405, 23, 19, { color: C.navy, bold: true, align: "center" }); if (i < rag.length - 1) addText(s, "↓", 300, y + 55, 35, 24, 22, { color: C.green, bold: true, align: "center" }); y += 78; });
  addText(s, "Luna accompagne le visiteur : conseil, simulation et prise de rendez-vous avec confirmation.", 90, 580, 500, 44, 18, { color: C.teal, bold: true });
  s.speakerNotes.textFrame.setText("Luna ne répond pas uniquement à partir d'un modèle de langage. Le RAG cherche d'abord des passages pertinents dans le corpus documentaire local avec ChromaDB. La réponse peut alors s'appuyer sur ces informations et guider le visiteur vers la bonne action.");
}

// 10 Demo + close
{
  const s = ppt.slides.add(); base(s, "Démonstration", 10); title(s, "Démonstration et conclusion", "Scénario proposé pour la vidéo de l'application");
  await img(s, "image29.png", 748, 155, 430, 390, "Résultat de simulation", "contain");
  const demo = [["1", "Accéder au catalogue et choisir une solution"], ["2", "Remplir le formulaire de simulation"], ["3", "Afficher le résultat, score et recommandations"], ["4", "Interroger Luna puis demander un rendez-vous"], ["5", "Montrer le suivi dans le dashboard administrateur"]];
  let y = 170;
  demo.forEach(([n, text]) => { rect(s, 82, y, 44, 44, C.green, "rounded-xl"); addText(s, n, 93, y + 8, 22, 24, 18, { color: C.white, bold: true, align: "center" }); addText(s, text, 145, y + 9, 550, 30, 19, { color: C.ink }); y += 68; });
  rect(s, 80, 555, 1090, 78, C.mint); addText(s, "EcoReno+ centralise l'information, la simulation, le chatbot et le suivi administratif dans une même plateforme.", 115, 580, 1020, 30, 21, { color: C.navy, bold: true, align: "center" });
  s.speakerNotes.textFrame.setText("Pour la vidéo, je montrerai ce scénario en cinq étapes. Je terminerai par le dashboard administrateur afin de montrer que les données sont bien suivies après la simulation. Merci pour votre attention.");
}

const candidatePath = path.join(buildDir, "ecoreno_candidate.pptx");
await (await PresentationFile.exportPptx(ppt)).save(candidatePath);
const requirements = { explicitTotalSlideCount: 10, requiredNativeTableOwnerSlides: [], requiredNativeChartOwnerSlides: [] };
const result = await finalizePresentation({
  ...requirements,
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit"],
  fontPolicy: { basis: "design", families: [font] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, "validation.json"),
});
console.log(JSON.stringify({ finalPath, result }, null, 2));
