# Interface graphique pour tiddl

## Contexte

`tiddl` (v3.4.4, installé dans `D:\Vibe Coding\tiddl\.venv`) est un outil en ligne de commande fonctionnel pour télécharger de la musique depuis Tidal. L'utilisateur préfère une interface à boutons plutôt que la CLI PowerShell pour un usage quotidien simple.

## Objectif

Une fenêtre Tkinter unique qui pilote `tiddl.exe` via `subprocess`, sans dupliquer sa logique interne. Priorité : simplicité, clarté, utilisable sans connaître la CLI.

## Approche technique

`subprocess.Popen` sur `D:\Vibe Coding\tiddl\.venv\Scripts\tiddl.exe`, sortie capturée en streaming et affichée dans un widget de log. Alternative écartée : importer les modules Python de `tiddl` directement — rejetée car `tiddl` est conçu comme CLI, pas comme bibliothèque, et son API interne n'est pas stable (on a déjà dû patcher un bug de modèle Pydantic dans `tiddl/models/auth.py`).

Le processus de téléchargement tourne dans un thread séparé pour ne jamais geler l'interface. Un seul téléchargement actif à la fois.

## Layout de la fenêtre

**Zone 1 — Connexion (haut)**
- Bouton "Se connecter" → lance `tiddl auth login`, affiche le lien `link.tidal.com` dans le log
- Indicateur texte "Connecté" / "Non connecté"

**Zone 2 — Téléchargement (milieu)**
- Bouton "Télécharger mes favoris" → `tiddl fav -r track download` (couvre tracks/albums/playlists/artistes par défaut, pas de filtre supplémentaire)
- Champ texte URL + bouton "Télécharger ce lien" → `tiddl url <URL> download`
- Menu déroulant qualité : Normal / High / Master (défaut : High)
- Champ dossier de destination, pré-rempli avec `C:\Users\BUREAU-ALEXIS\Music\Tiddl`, bouton "Parcourir…" (dialogue natif Windows)
- Bouton "Annuler" — actif seulement pendant un téléchargement, tue le sous-processus
- Bouton "Ouvrir le dossier" — actif après un téléchargement terminé, lance `explorer.exe` sur le dossier de destination

**Zone 3 — Log (bas)**
- Zone de texte défilante, auto-scroll, affiche la sortie brute de `tiddl` en direct

## Comportement

- Pendant un téléchargement : les boutons de lancement (favoris, lien, se connecter) sont désactivés ; "Annuler" est actif
- Fin de téléchargement (succès ou annulation) : boutons de lancement réactivés, "Ouvrir le dossier" devient actif
- Erreurs `tiddl` (ex. token expiré) : le message d'erreur apparaît tel quel dans le log, pas de traitement spécial

## Hors scope (explicitement exclu)

- Recherche par nom (`tiddl search`) — nécessiterait une liste de résultats cliquable, complexité jugée non justifiée
- Téléchargement par lot depuis fichier (`tiddl file`) — besoin non exprimé
- Filtrage par type de favori (tracks seuls vs albums seuls) — `fav download` télécharge déjà tout par défaut
- Barre de progression par piste, pause/reprise, file d'attente, multi-comptes

## Tests

Vérification manuelle dans le navigateur/l'app :
1. Connexion : le lien s'affiche, l'indicateur passe à "Connecté" après autorisation
2. Téléchargement par lien : fichier apparaît dans le dossier configuré
3. Téléchargement des favoris : log affiche la progression piste par piste
4. Annulation : le sous-processus s'arrête, boutons reviennent à l'état initial
5. Ouvrir le dossier : `explorer.exe` s'ouvre sur le bon chemin
6. Changement de dossier via "Parcourir…" : le nouveau chemin est utilisé pour le téléchargement suivant
