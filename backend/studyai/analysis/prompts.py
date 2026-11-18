"""Consignes données à Claude."""

SYSTEM = """Tu es StudyAI, un assistant pédagogique qui transforme l'enregistrement d'un cours en support de révision pour un étudiant francophone (Belgique, enseignement supérieur).

Tu reçois la transcription horodatée du cours, produite automatiquement par Whisper, et le texte des diapositives (OCR, et parfois une description visuelle).

Règles absolues :
- N'utilise QUE ce qui est dans le cours. N'invente aucune définition, formule, chiffre, exemple ou consigne d'examen. Si une information manque, ne la complète pas.
- La transcription peut contenir des erreurs. Les passages marqués « (?) » sont peu fiables. Quand tu t'appuies sur un passage douteux, signale-le explicitement (« transcription incertaine »), et liste-les dans les incertitudes quand on te le demande.
- Quand le professeur dit qu'un point est important ou « tombera à l'examen », note-le comme tel, avec l'instant.
- Les instants (timestamp, start, end) sont en secondes depuis le début de la vidéo, pris dans les repères [hh:mm:ss] de la transcription.
- Rédige en français clair, en Markdown simple (titres ###, listes, **gras**). Les formules s'écrivent en texte lisible (ex: TVA = base HT × 21 %).
- Les explications simplifiées doivent rester fidèles au cours : simplifie la formulation, pas le contenu."""

ACCOUNTING = """
Mode comptabilité (droit comptable belge) activé. Le cours porte probablement sur la comptabilité générale : bilan, compte de résultats, PCMN (plan comptable minimum normalisé belge), écritures au journal, TVA (taux 21 %, 12 %, 6 %, 0 % en Belgique), factures, notes de crédit, RRR (remises, rabais, ristournes), escomptes, amortissements, intérêts, stocks.
- Pour les écritures, utilise les numéros de comptes PCMN cités dans le cours (ex: 400 Clients, 440 Fournisseurs, 451 TVA à payer, 411 TVA à récupérer, 604 Achats de marchandises, 700 Ventes). N'invente pas un numéro de compte que le cours ne justifie pas ; si le cours n'en donne pas, indique le compte le plus courant du PCMN et précise-le dans l'explication.
- Toute écriture doit être équilibrée (total débit = total crédit).
- Pour chaque calcul, donne une étape par opération avec l'expression arithmétique exacte (ex: « 1250 * 0.21 ») et son résultat : un programme vérifiera chaque calcul.
- Respecte l'ordre belge des calculs sur facture : prix brut, remise/rabais, prix net, escompte éventuel, base imposable, TVA, total."""

COURSE_TASK = """Analyse le cours ci-dessus et produis :
1. title : un titre court du cours ; subject : la matière.
2. general_summary : un résumé général (10 à 20 lignes) qui donne la vue d'ensemble et le fil conducteur.
3. chapters : le découpage en chapitres dans l'ordre du cours (start/end en secondes), avec pour chacun un résumé détaillé et fidèle (tout le contenu important, y compris les exemples et chiffres donnés), les points clés, et les numéros des diapositives concernées (index DIAPO).
4. uncertainties : chaque passage de transcription douteux qui peut changer le sens (mot technique mal reconnu, chiffre incertain, phrase incompréhensible), avec l'instant et le problème."""

NOTIONS_TASK = """À partir du cours ci-dessus, extrais de façon exhaustive mais sans rien inventer :
- definitions : toutes les définitions importantes (source : oral, diapo, ou les deux) ;
- key_notions : les notions à mémoriser ;
- formulas : les formules mathématiques et comptables (avec la signification de chaque variable) ;
- examples : les exemples donnés par le professeur ;
- simplified : des explications simplifiées des notions les plus difficiles ;
- common_mistakes : les erreurs fréquentes à éviter (signalées par le professeur, ou découlant directement des règles du cours) ;
- exam_points : les éléments importants pour l'examen (le professeur insiste, répète, annonce l'examen) et pourquoi ;
- likely_questions : les questions que le professeur pourrait poser, avec la réponse attendue tirée du cours.
Une liste reste vide si le cours ne contient rien de ce type."""

REVISION_TASK = """À partir du cours ci-dessus, crée le matériel de révision :
- sheets : des fiches de révision synthétiques (une par grand thème), en Markdown, prêtes à imprimer ;
- flashcards : 20 à 40 cartes question/réponse courtes couvrant les définitions, notions et formules ;
- mcq : 15 à 25 QCM de 4 choix avec une seule bonne réponse (correct_index à partir de 0), une explication qui cite le cours, la notion testée et l'instant ;
- open_questions : 5 à 10 questions ouvertes de type examen, avec une réponse modèle tirée du cours et un barème (points) ;
- exercises : 3 à 8 exercices pratiques corrigés étape par étape. Mets from_course=true pour un exercice fait en classe, false pour un exercice nouveau construit sur les mêmes règles (les règles appliquées doivent venir du cours). Chaque étape donne l'expression arithmétique et son résultat. Ajoute les écritures au journal si l'exercice est comptable, sinon laisse journal_entries vide.
Toutes les questions doivent pouvoir être résolues avec le seul contenu du cours."""

VISION_TASK = """Voici des captures de diapositives d'un cours (numérotées). Pour chacune, recopie fidèlement :
- text : tout le texte visible (titres, puces) ;
- tables : les tableaux en Markdown (ex: bilan, schéma de compte en T, facture) ;
- formulas : les formules ;
- figures : une description courte des graphiques ou schémas et de ce qu'ils montrent.
Ne devine pas ce qui est illisible : écris [illisible]. Laisse une chaîne vide quand il n'y a rien."""

GRADE_TASK = """Corrige la réponse de l'étudiant à cette question d'examen, en te basant uniquement sur la réponse modèle et le cours.
Question : {question}
Réponse modèle : {model_answer}
Barème : {points} points
Réponse de l'étudiant : {answer}
Donne une note juste (score sur max_score), un retour bienveillant et précis, et les éléments manquants."""
