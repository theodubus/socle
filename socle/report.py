"""Le rapport d'un contrôle : une liste de constats et un seul code de sortie.

Tous les contrôles s'exécutent, même après un échec, et sont rapportés
ensemble : découvrir trois problèmes d'un coup coûte moins cher que trois
allers-retours.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from socle.messages import trad

# La ligne finale d'un rapport en échec, qui nomme les contrôles : relue par
# l'installeur, l'auto-test et le banc, dans toutes les langues.
LIGNE_ECHEC = re.compile(r"^(?:ECHEC — \d+ contrôle\(s\) : |FAILED — \d+ check\(s\): )(.+)$", re.M)

ERREUR = "erreur"
AVERTISSEMENT = "avertissement"
INDISPONIBLE = "indisponible"


@dataclass
class Constat:
    controle: str
    message: str
    chemin: str | None = None
    ligne: int | None = None
    gravite: str = ERREUR
    # La valeur que le constat cite (un identifiant, la cible d'un lien, le
    # nom d'un test) : la clé sous laquelle l'adoption le tolère, sans
    # dépendre de la langue ni de la tournure du message (B-0180).
    objet: str | None = None
    # La ligne commune que l'affichage regroupé imprime une fois à la place
    # des constats d'une même cause qui la portent (B-0196, ADR-0077).
    regroupe: str | None = None

    def lieu(self) -> str:
        if self.chemin and self.ligne:
            return f"{self.chemin}:{self.ligne}"
        return self.chemin or ""

    def en_ligne(self) -> str:
        lieu = self.lieu()
        return f"{lieu} — {self.message}" if lieu else self.message


@dataclass
class Rapport:
    constats: list[Constat] = field(default_factory=list)
    executes: list[str] = field(default_factory=list)

    def erreur(self, controle, message, chemin=None, ligne=None, objet=None, regroupe=None):
        self.constats.append(Constat(controle, message, chemin, ligne, ERREUR, objet, regroupe))

    def avertir(self, controle, message, chemin=None, ligne=None, objet=None):
        self.constats.append(Constat(controle, message, chemin, ligne, AVERTISSEMENT, objet))

    def indisponible(self, controle, message):
        """Un contrôle qui ne peut pas s'exécuter le DIT, au lieu d'être sauté
        en silence (règle 5 des emplacements de mémoire)."""
        self.constats.append(Constat(controle, message, None, None, INDISPONIBLE))

    def execute(self, controle):
        if controle not in self.executes:
            self.executes.append(controle)

    def fusionner(self, autre: "Rapport"):
        self.constats.extend(autre.constats)
        for c in autre.executes:
            self.execute(c)

    def erreurs(self, controle: str | None = None) -> list[Constat]:
        return [
            c for c in self.constats
            if c.gravite == ERREUR and (controle is None or c.controle == controle)
        ]

    @property
    def reussi(self) -> bool:
        return not self.erreurs()

    def controles_en_echec(self) -> list[str]:
        vus = []
        for c in self.erreurs():
            if c.controle not in vus:
                vus.append(c.controle)
        return vus

    def texte(self, titre: str | None = None, court: bool = False, regrouper: bool = False) -> str:
        """Le rapport, contrôle par contrôle ; `court` n'en montre que ce qui
        échoue, avertit ou n'a pas pu s'exécuter, et compte le reste ;
        `regrouper` imprime une fois, à leur place, la ligne commune des
        constats qui en portent une (ADR-0077)."""
        lignes = []
        dites = set()
        tus = 0
        if titre:
            lignes.append(titre)
            lignes.append("")
        noms = list(self.executes)
        for c in self.constats:
            if c.controle not in noms:
                noms.append(c.controle)
        for nom in noms:
            siens = [c for c in self.constats if c.controle == nom]
            erreurs = [c for c in siens if c.gravite == ERREUR]
            avert = [c for c in siens if c.gravite == AVERTISSEMENT]
            indispo = [c for c in siens if c.gravite == INDISPONIBLE]
            if erreurs:
                etat = trad("ECHEC")
            elif indispo:
                etat = trad("indisponible")
            elif avert:
                etat = trad("ok (avertissement)")
            else:
                etat = "ok"
            if court and not (erreurs or avert or indispo):
                tus += 1
                continue
            lignes.append(f"  {nom:<34} {etat}")
            for c in erreurs + avert + indispo:
                marque = {ERREUR: "|", AVERTISSEMENT: "!", INDISPONIBLE: "?"}[c.gravite]
                if regrouper and c.regroupe:
                    if (nom, c.regroupe) not in dites:
                        dites.add((nom, c.regroupe))
                        lignes.append(f"      {marque} {c.regroupe}")
                    continue
                lignes.append(f"      {marque} {c.en_ligne()}")
        if court and tus:
            lignes.append(trad("  … et {n} autre(s) contrôle(s) sans rien à signaler", n=tus))
        lignes.append("")
        if self.reussi:
            lignes.append(trad("TOUT PASSE"))
        else:
            echecs = self.controles_en_echec()
            lignes.append(trad("ECHEC — {n} contrôle(s) : {controles}", n=len(echecs), controles=", ".join(echecs)))
        return "\n".join(lignes)

    def afficher(self, titre: str | None = None, flux=None, court: bool = False):
        print(self.texte(titre, court), file=flux or sys.stdout)


def en_echec_dans(sortie: str) -> list[str]:
    """Les contrôles en échec que nomme la sortie d'un rapport, quelle que soit
    sa langue ; vide si tout passe."""
    m = LIGNE_ECHEC.search(sortie or "")
    return [c.strip() for c in m.group(1).split(",")] if m else []
