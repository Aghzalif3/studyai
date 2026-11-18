# StudyAI

**Dépose une vidéo de cours, clique sur « ANALYSER MON COURS », et récupère un cours structuré, des fiches, des flashcards, des QCM, des exercices corrigés et un examen blanc.**

StudyAI tourne sur ton Mac. La transcription (Whisper), la détection des diapositives et l'OCR sont **locales et gratuites**. L'analyse intelligente utilise **Claude** (API payante à l'usage) ou, si tu veux zéro frais, un **modèle local gratuit** via Ollama (qualité moindre).

---

## Lancer StudyAI (Mac)

1. Télécharge le projet : bouton vert **Code → Download ZIP** sur GitHub, puis décompresse-le (ou `git clone https://github.com/Aghzalif3/studyai.git`).
2. **Double-clique sur `StudyAI.command`.**
   - Si macOS bloque le fichier (« développeur non identifié ») : clic droit → **Ouvrir** → **Ouvrir**. Une seule fois.
3. Au premier lancement, StudyAI installe tout seul ce qui manque (5 à 15 minutes) : Homebrew, FFmpeg, Node.js, uv, Python 3.12, Whisper et l'interface. Ton mot de passe Mac peut être demandé pour Homebrew.
4. Le navigateur s'ouvre sur **http://127.0.0.1:8765**. Laisse la fenêtre du Terminal ouverte pendant l'utilisation ; ferme-la pour quitter.

Après la première installation, une application **StudyAI** apparaît aussi dans `~/Applications` (Launchpad, Spotlight) : tu n'as plus besoin d'ouvrir le dossier.

> Le modèle Whisper *turbo* (≈ 1,6 Go) est téléchargé automatiquement à la première transcription. Ensuite tout fonctionne hors ligne.

## Configurer l'analyse intelligente (facultatif)

Sans configuration, tu as déjà : transcription horodatée, diapositives + OCR, lecteur synchronisé, exports TXT / SRT / PDF.

Pour le résumé, les notions, les fiches, les QCM, les exercices et l'examen blanc, choisis dans **Réglages** :

| Option | Coût | Qualité | Ce qu'il faut |
|---|---|---|---|
| **Claude (API)** | ≈ 0,50 à 1,50 $ par cours de 2 h avec Claude Opus 5.5 (≈ 0,05 $ avec Haiku 5.5) | La meilleure | Une clé API |
| **Modèle local (Ollama)** | Gratuit | Nettement moindre, plus lent | L'app [Ollama](https://ollama.com/download) + un modèle (installable depuis Réglages) |

**Important : l'abonnement Claude Pro ne donne pas accès à l'API.** Ce sont deux produits séparés. Pour utiliser Claude dans StudyAI :

1. Va sur [console.anthropic.com](https://console.anthropic.com/settings/keys), crée un compte et ajoute un peu de crédit (paiement à l'usage, par exemple 5 $).
2. Crée une clé API (elle commence par `sk-ant-`).
3. Colle-la dans **Réglages** de StudyAI. Elle est enregistrée dans le fichier local `.env` (jamais envoyé sur GitHub, jamais écrit dans le code).

Le coût estimé s'affiche avant chaque analyse, et le coût réel est indiqué sur chaque cours.

## Fonctionnalités

**Importation** : glisser-déposer de vidéos (MP4, MOV, MKV, AVI, WEBM…) ou d'audios (MP3, WAV, M4A, FLAC…), un ou plusieurs fichiers à la fois (traitement par lots). Barre de progression et temps restant estimé.

**Transcription (Whisper)** :
- Modèle *turbo* par défaut, autres modèles au choix (large-v3, medium, small, base, tiny).
- Moteur **mlx-whisper** sur Mac Apple Silicon (les modèles OpenAI Whisper, accélérés par la puce M1/M2/M3/M4), **faster-whisper** sur Mac Intel. Le paquet officiel `openai-whisper` est disponible en option (`uv sync --extra openai`), mais il est plus lent sur Mac.
- Détection automatique de la langue, vocabulaire comptable pour améliorer le français technique.
- Passages douteux repérés (faible confiance) et soulignés ; correction en un clic dans la transcription.
- Filtrage des « hallucinations » connues de Whisper sur les silences.
- Exports TXT, SRT et PDF.

**Diapositives** :
- Captures automatiques et détection des changements de diapositive (seuil adaptatif : si la vidéo filme le professeur, StudyAI ne prend pas chaque geste pour une nouvelle diapo).
- OCR gratuit avec **Apple Vision** (intégré à macOS, très bon en français), Tesseract en secours.
- En option, lecture par Claude (vision) : tableaux recopiés, formules, description des graphiques.
- Chaque diapositive est placée dans la transcription au moment où elle apparaît : Claude analyse ce que dit le professeur **et** ce qui est affiché.

**Analyse (Claude ou modèle local)** :
1. Résumé général ; 2. résumé détaillé par chapitre (avec horodatage) ; 3. définitions ; 4. notions à mémoriser ; 5. formules ; 6. exemples du professeur ; 7. explications simplifiées ; 8. erreurs fréquentes ; 9. éléments importants pour l'examen ; 10. questions probables avec réponses.
- Consigne stricte : n'utiliser que le contenu du cours, et signaler les incertitudes de transcription.
- Chaque élément renvoie au bon moment de la vidéo.

**Révision** : fiches imprimables, flashcards avec répétition espacée, QCM, examen blanc chronométré (QCM + questions ouvertes corrigées par Claude ou auto-évaluées), exercices corrigés étape par étape, suivi des résultats et des notions difficiles.

**Mode comptabilité** : bilan, compte de résultats, PCMN, écritures, TVA, factures, notes de crédit, RRR, escomptes, amortissements, intérêts, stocks.
- **Les calculs ne sont pas laissés à l'IA** : chaque étape d'exercice contient une expression que StudyAI recalcule en Python. Une erreur est signalée avec le bon résultat.
- Les écritures sont contrôlées (équilibre débit = crédit, classes 1 à 7 du PCMN).
- Page **Outils compta** : facture (remise, rabais, escompte, TVA belge sur base diminuée de l'escompte), TVA depuis TVAC, plans d'amortissement linéaire et dégressif, intérêts simples et composés, calculatrice.

**Vidéos longues** : audio découpé en segments de 10 minutes, la vidéo n'est jamais chargée en mémoire (FFmpeg travaille en flux), chaque étape est enregistrée dans SQLite. Si tu fermes StudyAI ou si le Mac s'éteint, le traitement **reprend là où il s'était arrêté** au prochain lancement.

## Temps de traitement (ordre de grandeur, cours de 2 h)

| Étape | Mac M1/M2/M3 | Mac Intel |
|---|---|---|
| Transcription Whisper turbo | 10 à 20 min | 1 à 2 h (préférer *small*) |
| Diapositives + OCR | 2 à 5 min | 5 à 10 min |
| Analyse Claude | 3 à 6 min | 3 à 6 min |
| Analyse modèle local (8B) | 15 à 40 min | déconseillé |

## Architecture

```
┌──────────────── Navigateur (http://127.0.0.1:8765) ────────────────┐
│ Interface Next.js (exportée en fichiers statiques)                 │
│ tableau de bord · import · lecteur synchronisé · révision · outils │
└───────────────────────────────┬────────────────────────────────────┘
                                │ /api
┌───────────────────────────────▼────────────────────────────────────┐
│ Moteur Python FastAPI (backend/studyai)                            │
│  pipeline/runner.py   file de tâches + reprise (SQLite)            │
│  pipeline/media.py    FFmpeg : probe, audio par segments, images   │
│  pipeline/transcribe.py  Whisper (mlx / faster / openai)           │
│  pipeline/slides.py   détection des diapositives + OCR             │
│  analysis/analyze.py  Claude (cache du cours) ou Ollama (morceaux) │
│  analysis/accounting.py  vérification des calculs et écritures     │
│  revision.py          répétition espacée, statistiques             │
│  exports.py           TXT, SRT, PDF, Markdown                      │
└────────────────────────────────────────────────────────────────────┘
        data/  (ignoré par git) : studyai.db, vidéos, diapositives
```

Les appels à Claude utilisent les sorties structurées (JSON validé par un schéma) et le **cache de prompt** : la transcription n'est facturée en plein qu'une fois pour les trois analyses.

## Développement

```bash
# Moteur (Python 3.12 via uv)
cd backend && uv sync && uv run uvicorn studyai.main:app --port 8765 --reload
# Interface avec rechargement à chaud (transmet /api au moteur)
cd frontend && npm install && npm run dev      # http://localhost:3000

# Tests
cd backend && uv run pytest                    # pipeline, API, compta, reprise, Ollama…
cd frontend && npm test && npm run lint
```

Les tests créent de vraies vidéos de test avec FFmpeg (diapositives + son) et vérifient toute la chaîne : import, découpage, détection des diapositives, OCR, analyse (Claude simulé), vérification comptable, exports PDF/SRT, flashcards, reprise après une coupure.

## Limites connues

- Pas d'abonnement Whisper nécessaire, mais le **premier** usage télécharge le modèle (Internet requis une fois).
- La qualité dépend du son : un micro lointain ou une salle bruyante donne plus de passages douteux (ils sont signalés).
- La détection des diapositives fonctionne pour les captures d'écran et les vidéos de projection ; pour un professeur filmé au tableau, elle prend moins d'images (seuil adaptatif) et l'OCR du tableau manuscrit est limité.
- Le modèle local gratuit fait des résumés moins fiables et peut se tromper dans les exercices : la vérification automatique des calculs reste active, mais relis avec ton cours.
- Un cours de plus de ~10 h doit être découpé en plusieurs fichiers pour l'analyse.

## Données et vie privée

Tout reste dans le dossier `data/` sur ton Mac. Seul le texte du cours (et les images des diapositives si tu actives la lecture par Claude) est envoyé à l'API Anthropic quand tu choisis Claude. Avec le modèle local, rien ne quitte ton ordinateur.

## Licences

Code StudyAI. Utilise [OpenAI Whisper](https://github.com/openai/whisper) (MIT), [mlx-whisper](https://github.com/ml-explore/mlx-examples) (MIT), [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT), [FFmpeg](https://github.com/FFmpeg/FFmpeg) (LGPL/GPL, installé via Homebrew), [ocrmac](https://github.com/straussmaximilian/ocrmac) (MIT).
