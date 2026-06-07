"""Nettoie le registre HA pour le Cookeo : entry « Cookeo » + purge des entités/devices
de l'ancienne découverte (nom MAC), pour régénérer des entity_id propres `cookeo_*`.
Exécuté sur le Pi HA pendant que le core est ARRÊTÉ. Sauvegarde *.cookeobak d'abord.
"""
import json
import shutil
import sys

S = "/config/.storage/"
files = ["core.config_entries", "core.entity_registry", "core.device_registry"]

# 1) charge + valide tout avant d'écrire
data = {}
for f in files:
    with open(S + f, encoding="utf-8") as fh:
        data[f] = json.load(fh)

ce = data["core.config_entries"]["data"]["entries"]
cookeo_ids = [e["entry_id"] for e in ce if e["domain"] == "cookeo"]
if not cookeo_ids:
    print("Aucun config entry cookeo — abandon")
    sys.exit(0)

# 2) backups
for f in files:
    shutil.copy(S + f, S + f + ".cookeobak")

# 3) entry -> titre propre
for e in ce:
    if e["domain"] == "cookeo":
        e["title"] = "Cookeo"

# 4) purge entités plateforme cookeo
er = data["core.entity_registry"]["data"]
before = len(er["entities"])
er["entities"] = [x for x in er["entities"] if x.get("platform") != "cookeo"]
print("entités cookeo purgées:", before - len(er["entities"]))

# 5) purge devices cookeo
dr = data["core.device_registry"]["data"]
def is_cookeo(dev):
    for ident in dev.get("identifiers", []):
        if ident and ident[0] == "cookeo":
            return True
    return dev.get("primary_config_entry") in cookeo_ids
bdev = len(dr["devices"])
dr["devices"] = [d for d in dr["devices"] if not is_cookeo(d)]
print("devices cookeo purgés:", bdev - len(dr["devices"]))

# 6) écrit
for f in files:
    with open(S + f, "w", encoding="utf-8") as fh:
        json.dump(data[f], fh)
print("OK — registres réécrits, entry renommée 'Cookeo'")
