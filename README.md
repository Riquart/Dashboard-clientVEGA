# Dashboard de suivi clientèle — Licences & PS abonnés

Application web qui lit un fichier Excel de suivi et affiche un tableau de bord
interactif (activité réelle des abonnés / non-abonnés, parc de licences,
tendances par profession et par période). Le fichier Excel peut être mis à jour
en ligne, **sans redéploiement**.

## Comment ça marche

- **`app.py`** — petite application Flask. Sert le dashboard et expose les
  données via `/api/data`. Permet de remplacer l'Excel via `/upload`.
- **`dashboard_data.py`** — lit la feuille « Données » de l'Excel et la transforme
  en JSON (agrégation hebdomadaire, robuste aux relevés journaliers aberrants).
- **`static/index.html`** — le dashboard (graphiques Chart.js). Récupère les
  données depuis `/api/data`.
- **`data/source.xlsx`** — le fichier Excel livré par défaut.
- **`data/cache.json`** — résultat pré-calculé du fichier livré (démarrage instantané).

Le parsing de l'Excel prend ~15 s. Il n'est fait **qu'une seule fois** par version
du fichier (cache par empreinte MD5), puis mis en cache mémoire + disque.

## Lancer en local

```bash
pip install -r requirements.txt
# (option) mot de passe pour la page d'upload :
export UPLOAD_TOKEN="choisis-un-mot-de-passe"
python app.py
# -> http://localhost:8000
```

## Déployer sur Railway

1. **Pousser le projet sur GitHub** (voir section suivante).
2. Sur [railway.com](https://railway.com) : **New Project → Deploy from GitHub repo**,
   choisir ce dépôt. Railway détecte Python (Nixpacks) et installe `requirements.txt`.
3. La commande de démarrage est déjà définie (`Procfile` + `railway.json`) :
   `gunicorn app:app --timeout 120 --workers 2`.
4. **Ajouter un volume persistant** (pour que les Excel uploadés survivent aux
   redéploiements) : service → **Variables/Settings → Volumes → New Volume**,
   point de montage **`/data`**.
5. **Variables d'environnement** (service → Variables) :
   - `DATA_DIR` = `/data`  (le volume)
   - `UPLOAD_TOKEN` = un mot de passe de ton choix (protège `/upload`)
6. **Générer un domaine public** : Settings → Networking → **Generate Domain**.
7. Ouvrir l'URL → le dashboard s'affiche (instantané grâce au cache livré).

> Sans volume, l'app fonctionne quand même avec le fichier livré, mais un Excel
> uploadé serait perdu au prochain redéploiement. Le volume est donc recommandé.

## Mettre à jour les chiffres

Trois options, de la plus simple à la plus « dev » :

1. **Page d'upload (recommandé)** — aller sur `…/upload`, déposer le nouveau
   `.xlsx`, saisir le `UPLOAD_TOKEN`. Le site se met à jour tout de suite
   (le 1er chargement reparse, ~15 s). Aucun redéploiement.
2. **Remplacer `data/source.xlsx`** dans le dépôt et `git push` → Railway
   redéploie automatiquement. (Pense à supprimer `data/cache.json` ou il sera
   recalculé tout seul à la 1re visite.)
3. **Modifier `dashboard_data.py`** si la structure de l'Excel change (nouvelles
   lignes/indicateurs).

## Pousser sur GitHub

```bash
git init
git add .
git commit -m "Dashboard suivi clientèle"
git branch -M main
git remote add origin https://github.com/<ton-compte>/<ton-repo>.git
git push -u origin main
```

## Bon à savoir

- La date de fin de prise en compte des données est `CUTOFF` dans
  `dashboard_data.py` (actuellement 2026-05-25). À avancer si l'Excel va plus loin.
- Les indicateurs « actifs » = *connectés sur 30 jours glissants* (présents dans
  l'Excel). C'est ce qui permet de distinguer les non-abonnés vivants des comptes
  dormants.
- Les pourcentages sont recalculés à partir des effectifs (pour neutraliser les
  `#DIV/0!` du fichier d'origine).
