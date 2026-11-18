#!/bin/bash
# StudyAI : double-clique sur ce fichier pour lancer l'application.
# Au premier lancement, il installe tout ce qu'il faut (5 à 15 minutes), ensuite il démarre en quelques secondes.
cd "$(dirname "$0")" || exit 1
exec bash scripts/start.sh "$@"
