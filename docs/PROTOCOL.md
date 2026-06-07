# Protocole BLE Cookeo Connect (reverse-engineering)

Source : décompilation de `com.groupeseb.moncookeo` (package `com.groupeseb.cookeat.addons.cookeo.ble`).
Validé : pilotage end-to-end le 07/06/2026 (le Cookeo répond `01 02 01 01 3B C4`).

## Appareil
- Nom BLE : `BLuE Cookeo`. Connexion **sans appairage initial** possible, mais
  l'app **bonde** l'appareil (`COOKEO_PAIRING_MODE = 2`) et les écritures ne sont
  honorées qu'une fois **appairé (bonded)**.

## GATT — service `3c63cc60-364a-11e3-808b-0002a5d5c51b`
| Caractéristique | UUID | Rôle |
|---|---|---|
| WRITE | `471846e0-364a-11e3-a7ad-0002a5d5c51b` | commandes (write) |
| NOTIFY/READ | `4fcc0f60-364a-11e3-98e0-0002a5d5c51b` | état/réponses |
| ACCESS | `672b49c0-d053-11e3-ad6e-0002a5d5c51b` | déverrouillage (write) |

## Handshake (ORDRE CRUCIAL)
1. **Appairer** (bond) l'appareil à l'adaptateur.
2. **Connecter**.
3. Écrire le **code d'accès** `00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F` sur **ACCESS**.
4. **Activer les notifications** sur NOTIFY (après le code d'accès, sinon muet).
5. Envoyer les **commandes** sur WRITE → réponses sur NOTIFY.

## Trame
`[LEN sur 2 octets][payload]` puis **+ CRC16-CCITT** (poly `0x1021`, init `0x0000`, MSB-first, 2 octets).
La réponse suit le même format `[payload][CRC16]`.

```python
def crc16_ccitt(data: bytes) -> int:
    crc = 0
    for b in data:
        for i in range(8):
            bit = (b >> (7 - i)) & 1
            c15 = (crc >> 15) & 1
            crc = (crc << 1) & 0xFFFF
            if bit ^ c15:
                crc ^= 0x1021
    return crc & 0xFFFF
```

## Commandes (payload, avant CRC)
| Action | Payload | Trame complète |
|---|---|---|
| Demander l'état | `00020065` | `000200655263` |
| Demander config | `00020301` | `000203012B12` |
| Version recette | `0002030B` | `0002030B8A58` |
| Stopper recette | `0002030A` | `0002030A9A79` |
| Envoyer « OK » | `00020303` | `000203030B50` |
| Annuler transfert | `00020202` | … |
| Démarrer recette | `000D0302` + `01` + type(s) plat + id(8) + `00000000` + qté(2) | + CRC |

## Transfert d'une recette (binaire `.cok`)
1. Header : `000F`(recette)/`000E`(pack) + `02` + `00` + id(8) + verMaj(2) + verMin(2) + lang(4 ascii→hex) + region(4) + nbChunks(4) + cat(2).
2. Données : chunks de 17 octets → `03`(recette)/`02`(pack) + chunk(34 hex, padué) + **CRC16**.
3. `startRecipe`.

## Binaires recette — catalogue SEB (PUBLIC, sans auth)
- `GET https://sebplatform.api.groupe-seb.com/statics/original/<uuid>.cok` → magic ASCII `COOK`.
- Métadonnées : `GET https://sebplatform.api.groupe-seb.com/common-api/v3/recipes/PRO/{variantId}/`.

## Programmes (mode manuel — `CookeoConstants.Program`)
`BROWNING_LOW/MEDIUM/HIGH`, `KEEP_WARM`, `COOKING_(ULTRA_)HIGH/LOW_PRESSURE`,
`STEAM`, `SIMMERING_*`, `SLOW_COOKING`, `REHEAT` (technicalId `PROGRAM_2000xx`).
