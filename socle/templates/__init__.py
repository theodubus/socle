"""Gabarits que l'installeur pose dans un projet."""

from pathlib import Path

DOSSIER = Path(__file__).resolve().parent


def gabarit(nom: str, langue: str = "fr") -> str:
    """Le gabarit, dans la langue de la mémoire du projet quand il en a une
    version (`request.en.md` pour `request.md`) ; sinon en français."""
    if langue != "fr":
        p = DOSSIER / nom
        traduit = p.with_name(f"{p.stem}.{langue}{p.suffix}")
        if traduit.is_file():
            return traduit.read_text(encoding="utf-8")
    return (DOSSIER / nom).read_text(encoding="utf-8")
