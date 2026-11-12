"""Les messages du moteur dans la langue du projet.

Un message s'écrit en français dans le code, enveloppé par `trad` ; le texte
français est la clé du catalogue d'une autre langue (`messages_en.py`). La
langue est celle de la mémoire du projet (`[memory] language`), posée par la
ligne de commande quand elle charge un projet. Un message absent du
catalogue sort en français : rien ne casse, et un test exige qu'il n'en
manque aucun.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar

FRANCAIS = "fr"
# Une variable de contexte, pas un global : chaque fil part du français, et
# la langue qu'un fil pose (l'auto-test en lance plusieurs) ne passe pas aux
# autres.
_courante: ContextVar[str] = ContextVar("langue_des_messages", default=FRANCAIS)
_VARIABLE = re.compile(r"\{(\w+)\}")


def _catalogue(langue: str) -> dict[str, str]:
    if langue == "en":
        from socle.messages_en import MESSAGES
        return MESSAGES
    return {}


def remplir(texte: str, valeurs: dict) -> str:
    """Remplace chaque `{nom}` dont la valeur est donnée ; une accolade dont
    le nom n'est pas donné reste telle quelle (un exemple de commande, du
    JSON)."""
    if not valeurs:
        return texte
    return _VARIABLE.sub(lambda m: str(valeurs[m.group(1)]) if m.group(1) in valeurs else m.group(0), texte)


class Message(str):
    """Un message traduit qui garde sa source française, remplie : la clé
    d'un constat que l'adoption tolère n'en dépend pas de la langue
    (B-0180)."""

    source: str


def source(message: str) -> str:
    """Le texte français d'un message, quelle que soit la langue où il est
    sorti."""
    return getattr(message, "source", message)


def trad(texte: str, /, **valeurs) -> str:
    """Le message dans la langue courante, ses variables remplies."""
    langue_ = _courante.get()
    if langue_ == FRANCAIS:
        return remplir(texte, valeurs)
    m = Message(remplir(_catalogue(langue_).get(texte, texte), valeurs))
    m.source = remplir(texte, {k: source(v) for k, v in valeurs.items()})
    return m


def a_traduire(texte: str) -> str:
    """Marque un texte défini loin de son emploi (une table, une constante) :
    il reste en français, et se traduit à l'emploi par `trad`. Le test du
    catalogue le lit comme un message."""
    return texte


def langue() -> str:
    return _courante.get()


def choisir(langue_: str | None) -> str:
    """Pose la langue des messages ; rend la précédente. Une langue sans
    catalogue retombe sur le français."""
    avant = _courante.get()
    _courante.set(langue_ if langue_ and (langue_ == FRANCAIS or _catalogue(langue_)) else FRANCAIS)
    return avant


@contextmanager
def dans(langue_: str | None):
    """Les messages dans une langue, le temps d'un bloc."""
    avant = choisir(langue_)
    try:
        yield
    finally:
        choisir(avant)
