<img src="icon.png" width="96" align="right" alt="Cookeo BLE">

# Cookeo BLE — intégration Home Assistant

Pilotez votre **Moulinex Cookeo Connect** (Bluetooth) depuis Home Assistant,
sans le cloud SEB. Protocole **reverse-engineeré** depuis l'app *Mon Cookeo*
(`com.groupeseb.moncookeo`) — communication BLE **en clair**.

> ⚠️ Projet non officiel, non affilié au Groupe SEB. Usage personnel, à vos risques.

## Ce que ça fait
- **Suivi de cuisson** : état, mode, progression (%), temps écoulé/restant, convives, étape.
- **Contrôle** : boutons *Arrêter* / *Valider (OK)* / *Demander l'état* ; service `start_recipe`.
- **Capteurs binaires** : cuisson en cours, maintien au chaud, recette active, erreur.
- **Envoi de recettes** : transfert d'un binaire `.cok` (en-tête `000F…` + chunks + CRC16) puis démarrage optionnel.
- **Recettes `.cok` publiques** : `https://sebplatform.api.groupe-seb.com/statics/original/<uuid>.cok`
  (téléchargeables sans authentification ; la *recherche* catalogue requiert une clé API).
- **Config** : boutons **🔗 Appairer** et **🧪 Tester la connexion** dans les options.

## Entités
| Plateforme | Entités |
|---|---|
| `sensor` | État, Mode, Progression, Temps restant/écoulé/total, Convives, Étape, Recette (id), Dernière trame |
| `binary_sensor` | Cuisson, Maintien au chaud, Recette en cours, Erreur |
| `button` | Arrêter, Valider (OK), Demander l'état |
| `number` | Convives par défaut |

## Services
- `cookeo.start_recipe` — `recipe_id`, `course`, `quantity`
- `cookeo.send_recipe` — `uuid` **ou** `url`, `recipe_id`, `version`, `category`, `start`, `course`, `quantity`
- `cookeo.search_recipe` — `query` (réponse de service ; clé API requise)
- `cookeo.send_command` — trame hex brute (CRC16 ajouté)

## Protocole (résumé)
- **Service** `3c63cc60-364a-11e3-808b-0002a5d5c51b`
  - **Write** `471846e0-…` (commandes) · **Notify** `4fcc0f60-…` (état) · **Access** `672b49c0-…`
- Trame = `payload hex` + **CRC16-CCITT** (poly `0x1021`, init `0`).
- **Octets d'une trame d'état** : `[type][len][catégorie][état][menu][mode][temps total 3o][temps écoulé 3o]…`
- **Handshake** : appairer (bond) → connecter → écrire le **code d'accès**
  `00 01 02 … 0F` sur *Access* → activer les **notifications** → envoyer les commandes.
- Exemple : `ASK_STATE` = `00020065` → trame `000200655263` → réponse `01 02 01 01 3B C4`.

Détails complets dans [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Installation (HACS)
1. HACS → Intégrations → ⋮ → *Dépôt personnalisé* → `https://github.com/juliewaymel/cookeo-ha` (type *Integration*).
2. Installer **Cookeo BLE**, redémarrer Home Assistant.
3. Réglages → Appareils & services → *Ajouter* → **Cookeo BLE** (découverte Bluetooth ou MAC).
4. **Appairer** : Options de l'intégration → *🔗 Appairer le Cookeo* (mettre le Cookeo en mode appairage), puis *🧪 Tester*.

## Tableau de bord (livré avec l'intégration)
- `dashboards/cookeo_dashboard.yaml` : vue **cartes natives** (aucune dépendance), jauges conditionnelles, minuteur, contrôles, carte d'envoi.
- `dashboards/cookeo_dashboard_mushroom.yaml` : vue **visuelle** (écran dégradé bordeaux, anneau de progression, chips). Requiert les cartes HACS **Mushroom**, **apexcharts-card**, **card-mod**.
- `dashboards/cookeo_helpers.yaml` : helpers + scripts pour envoyer/lancer une recette depuis l'UI (copier dans `config/packages/`, ou créer les helpers via l'UI).

## Catalogue de recettes (consultation)
Outils dans [`tools/catalog/`](tools/catalog/) :
- `harvest.py` : moissonne les recettes **officielles Cookeo FR** via l'API SEB (header `apikey`,
  fiche `/common-api/recipes/PRO/{fid}/`) → `catalog.json` (titre, photo HD, ingrédients,
  étapes avec programme/durée/température). Échantillonne l'espace d'ids (pas de liste publique),
  dédup par `groupingId`. Lancé en cron pour des MAJ incrémentales.
- `index.html` : page web autonome (grille + recherche + fiche), à servir en statique
  (nginx) et embarquer dans HA (`/local/` ou iframe).

## Statut
- ✅ Pilotage prouvé end-to-end (le Cookeo répond : état, stop, OK, suivi de cuisson).
- ✅ **Consultation** des recettes officielles : catalogue navigable (photos, ingrédients, étapes).
- ⛔ **Envoi d'une recette du catalogue : non disponible.** Le Cookeo n'accepte que le transfert
  de son binaire `.cok` propriétaire ; ces binaires ne sont **pas servis par l'API publique**
  (réservés à une session compte authentifiée). L'envoi `.cok` fonctionne uniquement si on
  connaît déjà l'UUID d'un binaire public (service `cookeo.send_recipe`, expérimental, à valider
  sur appareil appairé). Pas de cuisson manuelle pilotable (elle se fait sur l'écran du Cookeo).

## Crédits
Reverse-engineering & intégration : Julie Waymel. Décompilation jadx, analyse BLE via BlueZ.
