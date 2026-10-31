"""L'empreinte du moteur : rien ne s'altère en silence.

L'empreinte couvre le paquet `socle` (hors caches) et le lanceur. Elle est
enregistrée dans le verrou du moteur (`.socle/engine.lock`) à l'installation, et la CI la recalcule.
Un moteur modifié dans le projet ne se répare pas à la main : on relance
l'installeur, et le diff passe par une demande validée.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from socle import config


def fichiers_moteur(racine: Path, dossier_moteur: str) -> list[Path]:
    paquet = racine / dossier_moteur / "socle"
    # Ni les caches, ni les fichiers cachés (un `.DS_Store` du clone source) :
    # l'installeur ne les copie pas, un clone frais ne les a pas.
    res = [
        p for p in paquet.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        and not any(x.startswith(".") for x in p.relative_to(paquet).parts)
    ]
    lanceur = racine / config.LANCEUR
    if lanceur.is_file():
        res.append(lanceur)
    return sorted(res)


def calculer(racine: Path, dossier_moteur: str) -> tuple[str, int]:
    h = hashlib.sha256()
    fichiers = fichiers_moteur(racine, dossier_moteur)
    for p in fichiers:
        rel = str(p.relative_to(racine)).replace("\\", "/")
        h.update(rel.encode("utf-8") + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return "sha256:" + h.hexdigest(), len(fichiers)


def fichier(chemin: Path) -> str:
    return "sha256:" + hashlib.sha256(chemin.read_bytes()).hexdigest()


def courte(empreinte: str) -> str:
    """La forme qu'une demande cite : `sha256:` et seize caractères."""
    return empreinte[: len("sha256:") + 16]
