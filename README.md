# Renshū 練習 — logiciel de révision QCM

Logiciel Windows pour réviser les interros au format AMC (♣ : zéro, une ou plusieurs bonnes réponses).
Thème sombre « cockpit ». Écrit en Python avec Qt (PySide6), livré en `.exe`.

## Pourquoi ce logiciel

Je suis en L3 informatique, spécialité réseaux. Dans cette matière, les examens sont
uniquement des QCM, et ils demandent des connaissances très approfondies : une case
cochée à tort coûte des points, et il faut savoir précisément ce qu'on sait et ce qu'on
croit savoir. Relire le cours ne me disait rien de mon vrai niveau.

J'ai donc écrit Renshū pour suivre mon niveau chapitre par chapitre, voir ce que je
maîtrise et ce que je rate encore, et mesurer mes progrès dans le temps. *Renshū* 練習
veut dire « entraînement ».

## Lancer

- Double-clique sur le raccourci **Renshu** du Bureau. Il lance `main.py` avec `pythonw.exe` (Python, signé).
- Pourquoi pas directement le `.exe` ? Le **Contrôle intelligent des applications** de Windows 11 est activé sur ce PC :
  il bloque les programmes non signés, donc `dist\Renshu\Renshu.exe` peut être refusé
  (« Une stratégie de contrôle d'application a bloqué ce fichier »). Le `.exe` reste utile pour un autre PC.
- En ligne de commande : `python main.py`.

## Écrans

| Écran | Rôle |
|---|---|
| Accueil | tableau de bord : questions vues, maîtrisées, à revoir, dernière note ; réussite par chapitre (clic = réviser ce chapitre) ; courbe des notes d'interro blanche ; tes pièges ; dernières séances |
| Réviser | chapitres, annales seulement, nombre de questions ; correction après chaque question avec l'explication de chaque case |
| Interro blanche | minuteur, navigation libre entre les questions, aucune correction avant de rendre la copie, note sur 20 ; copie ramassée automatiquement à la fin du temps |
| Statistiques | boîtes de révision (Leitner), réussite par chapitre, questions les plus ratées, historique |
| Questions | rechercher, ajouter, modifier, dupliquer, supprimer ; nouveaux chapitres ; import / export JSON |
| Exporter / partager | QCM interactif en un seul fichier `.html` à envoyer aux camarades (s'ouvre dans n'importe quel navigateur, correction et explications incluses) ; sujet et corrigé au format du prof (grille du numéro d'étudiant, consignes, propositions sur deux colonnes ; corrigé avec cases barrées, « ? » pour les douteuses et explications). Même numéro de tirage = même sujet. Une question n'est jamais coupée entre deux pages |
| Réglages | barème (tout ou rien, ou pénalité par case), dossier des données, remise à zéro |

Couleurs de correction : vert = bien cochée, pointillés verts = oubliée, rouge = cochée à tort, orange = douteuse (ne compte pas).

Clavier : **A–H** pour cocher, **Entrée** pour valider / passer à la suivante, **← →** pendant une interro blanche.

## Mes données

Tout est dans `%APPDATA%\Renshu` (bouton « Ouvrir le dossier » dans Réglages) :
- `questions.json` : tes questions (même format que la version web, réutilisable dans les deux sens) ;
- `progression.json` : révision espacée, historique, réglages ;
- `sauvegardes/` : copies automatiques de tes questions (une par jour, avant un import, avant une suppression ; les 15 dernières) ;
- `erreurs.log` : détail des erreurs inattendues, s'il y en a.

Une seule fenêtre Renshū à la fois (sinon deux fenêtres écraseraient la progression).

Au premier lancement, les 54 questions de `data/questions.json` y sont copiées.

## Reconstruire le .exe

Double-clique sur `build.bat` (installe PySide6 et PyInstaller si besoin, lance les tests, construit `dist\Renshu\`).

## Tests

```
python -m unittest discover -s tests
```

43 tests : correction, barèmes, révision espacée, format des données, enregistrement, sauvegardes, export PDF, QCM HTML.

## Organisation

```
main.py              point d'entrée
renshu/core.py       logique pure (correction, barèmes, révision espacée, données) — testée
renshu/store.py      fichiers dans %APPDATA%\Renshu
renshu/theme.py      thème sombre (feuille de style Qt)
renshu/paper.py      sujet / corrigé en PDF (Qt, sans LaTeX)
renshu/share.py      QCM HTML autonome (modèle templates/qcm_standalone.html)
renshu/widgets.py    composants : proposition, question, graphiques
renshu/app.py        fenêtre et écrans
data/questions.json  questions livrées avec le logiciel
tools/make_icon.py   génère assets/renshu.ico
```
