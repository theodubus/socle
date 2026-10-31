#!/usr/bin/env python3
"""Lanceur du socle : `python3 .socle/socle <commande>`.

Posé par l'installeur et couvert par l'empreinte du moteur : ne pas le
modifier à la main. Il lit le verrou pour trouver le moteur, et passe la
racine du projet au moteur, quel que soit le répertoire courant.
"""
import sys

if sys.version_info < (3, 11):
    sys.exit("le socle exige Python 3.11 ou plus récent (tomllib) ; trouvé : " + sys.version.split()[0])

import tomllib  # noqa: E402
from pathlib import Path  # noqa: E402

ici = Path(__file__).resolve().parent
racine = ici.parent
verrou = ici / "engine.lock"
verrou = tomllib.loads(verrou.read_text(encoding="utf-8")) if verrou.is_file() else {}
sys.path.insert(0, str(racine / verrou.get("engine_dir", ".socle/engine")))

from socle.cli import main  # noqa: E402

sys.exit(main(["--root", str(racine), *sys.argv[1:]]))
