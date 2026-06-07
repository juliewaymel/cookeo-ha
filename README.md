# Cookeo BLE — intégration Home Assistant

Pilotez votre **Moulinex Cookeo Connect** (Bluetooth) depuis Home Assistant,
sans le cloud SEB. Protocole **reverse-engineeré** depuis l'app *Mon Cookeo*
(`com.groupeseb.moncookeo`) — communication BLE **en clair**.

> ⚠️ Projet non officiel, non affilié au Groupe SEB. Usage personnel, à vos risques.

## Ce que ça fait
- Connexion BLE locale au Cookeo (état, stop, validation « OK », suivi de cuisson).
- Envoi de recettes : transfert d'un binaire `.cok` (chunks + CRC16) puis démarrage.
- Les recettes `.cok` du catalogue Cookeo sont servies **publiquement** par SEB :
  `https://sebplatform.api.groupe-seb.com/statics/original/<uuid>.cok`.

## Protocole (résumé)
- **Service** `3c63cc60-364a-11e3-808b-0002a5d5c51b`
  - **Write** `471846e0-…` (commandes) · **Notify** `4fcc0f60-…` (état) · **Access** `672b49c0-…`
- Trame = `payload hex` + **CRC16-CCITT** (poly `0x1021`, init `0`).
- **Handshake** : appairer (bond) → connecter → écrire le **code d'accès**
  `00 01 02 … 0F` sur *Access* → activer les **notifications** → envoyer les commandes.
- Exemple : `ASK_STATE` = `00020065` → trame `000200655263` → réponse `01 02 01 01 3B C4`.

Détails complets dans [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Installation (HACS)
1. HACS → Intégrations → ⋮ → *Dépôt personnalisé* → `https://github.com/juliewaymel/cookeo-ha` (type *Integration*).
2. Installer **Cookeo BLE**, redémarrer Home Assistant.
3. Réglages → Appareils & services → *Ajouter* → **Cookeo BLE** (découverte Bluetooth ou MAC).
4. Pré-requis : le Cookeo doit être **appairé** à l'adaptateur Bluetooth de HA une fois.

## Statut
- ✅ Pilotage prouvé end-to-end (le Cookeo répond).
- 🚧 Entités/flux de config en cours de finalisation.

## Crédits
Reverse-engineering & intégration : Julie Waymel. Décompilation jadx, analyse BLE via BlueZ.
