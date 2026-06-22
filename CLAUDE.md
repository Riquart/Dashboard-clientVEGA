# Brief projet (pour Claude Code)

Petit dashboard web (Flask + Chart.js) qui lit un Excel de suivi clientèle CGM
et affiche l'activité réelle (abonnés / non-abonnés actifs, parc de licences,
tendances). Déployé sur Railway. Objectif : l'utilisateur (non-développeur)
modifie souvent les chiffres ; le site doit rester facile à mettre à jour.

## Architecture

```
app.py              Flask : routes / (dashboard), /api/data (JSON), /upload (form protégé), /healthz
dashboard_data.py   extract(xlsx_path) -> dict {profession: {labels, <8 métriques>}}
static/index.html   front-end ; fetch('/api/data') puis rend les graphiques
static/chart.umd.js Chart.js vendu localement (pas de CDN)
data/source.xlsx    Excel livré par défaut
data/cache.json     {hash, data} pré-calculé pour le fichier livré
requirements.txt / Procfile / railway.json   déploiement
```

## Flux de données

1. `app.get_data()` choisit le fichier actif : `DATA_DIR/source.xlsx` (uploadé)
   sinon `data/source.xlsx` (livré).
2. Cache par empreinte MD5 : mémoire → `cache.json` (volume puis livré) → sinon
   parse complet (~15 s) via `dashboard_data.extract`, puis écrit le cache.
3. `/api/data` renvoie `{meta, data}`. Le front rend tout côté client.

## Données (feuille « Données »)

- Organisée en blocs par profession (Infirmier, Kiné, Orthophoniste, Orthoptiste,
  Pédicure-Podologue, Total). En-tête de bloc : col A = nom, cols suivantes = dates.
- ~42 indicateurs par bloc. On extrait 8 séries : base et « connectés mois glissant »
  (= actifs 30 j), pour PS et licences, abonnés / non-abonnés.
- Agrégation **hebdomadaire** = médiane des valeurs journalières de la semaine ISO
  (robuste aux relevés corrompus, ex. 28/02/2018).
- `Total` est forcé = somme des 5 professions quand toutes présentes.
- `CUTOFF` (2026-05-25) borne la fin ; `LOWER` (2015) ignore une date aberrante (1926).

## Gotchas

- **Ne pas** charger l'Excel avec `read_only=True` (accès aléatoire aux cellules
  catastrophique sur ce fichier ~3000 colonnes → load standard `data_only=True`).
- Le système de fichiers Railway est **éphémère** : les uploads doivent aller sur
  un **volume** monté sur `/data` (`DATA_DIR=/data`). Sinon perdus au redéploiement.
- Si on remplace `data/source.xlsx`, supprimer `data/cache.json` (sinon hash ≠ et
  il se régénère seul de toute façon, mais autant rester propre).
- `UPLOAD_TOKEN` doit être défini pour activer `/upload`.

## Idées d'évolution probables

- Indicateur de **conversion** (non-abonnés → abonnés sur la période).
- Export PNG/PDF des graphiques ; vue COPIL imprimable.
- Auth plus robuste sur `/upload` (actuellement simple token).
- Comparaison entre périodes (N vs N-1).
