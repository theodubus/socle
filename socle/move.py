"""La bascule d'une entrée publique dans la mémoire privée :
`socle private move <ID>`. Une copie privée reprend son titre et son
texte ; l'entrée publique garde son identifiant, pour que les renvois
restent valides. Séparée de `prive`, qui lit et contrôle la zone privée."""

from __future__ import annotations

from socle import config, language as langue, memory as memoire, utils as outils
from socle.messages import trad
from socle.private import acces, mode

# Les entrées qu'une bascule déplace : une demande se lit là où l'humain lit,
# elle se retire et se pose à nouveau en privé.
BASCULABLES = ("F", "B", "J", "ADR")


def basculer(projet: config.Projet, ident: str, jour: str) -> list[str]:
    """Bascule une entrée publique dans la mémoire privée : une copie privée,
    sous un identifiant privé, en reprend le titre et le texte et cite
    `depuis : <identifiant>` ; l'entrée publique garde son identifiant, pour
    que les renvois restent valides, et perd son titre et son texte. Refuse
    ce qu'elle ne sait pas déplacer sans casser un renvoi. Rend ce qu'il faut
    dire à l'humain."""
    racine, ch = projet.racine, projet.chemins
    if mode(projet) is None:
        raise ValueError(trad("aucune mémoire privée dans la politique (`[private] mode`) : rien où basculer"))
    a = acces(projet)
    if not a.disponible:
        raise ValueError(trad("mémoire privée indisponible : {raison}", raison=a.raison))
    mem = memoire.Memoire.charger(racine)
    e = mem.entree(ident)
    if e is None:
        raise ValueError(trad("`{ident}` ne désigne aucune entrée de la mémoire", ident=ident))
    if e.prive or e.basculee:
        raise ValueError(trad("`{ident}` est déjà privée", ident=ident))
    if e.type == "D":
        raise ValueError(trad("une demande se lit là où l'humain lit : la retirer (`retirée : <raison>` dans "
                              'ses métadonnées) et en poser une privée (`socle new request "…" --private`)'))
    if e.type not in BASCULABLES:
        raise ValueError(trad("`{ident}` : seuls un fait, un sujet, une entrée de journal ou une décision se "
                              "basculent", ident=ident))
    if e.archivee:
        raise ValueError(trad("`{ident}` est archivée dans `{parent}` : c'est cette entrée de journal qui se "
                              "bascule", ident=ident, parent=e.parent))
    enfants = [x.id for x in mem.entrees() if x.parent == ident]
    if enfants:
        raise ValueError(trad("`{ident}` archive {liste}, que d'autres entrées citent peut-être : leurs "
                              "renvois publics ne survivraient pas à la bascule",
                              ident=ident, liste=', '.join(enfants)))
    nouvel = mem.prochain_id(e.type, prive=True, date=e.id[2:12] if e.type == "J" else None)
    lg = langue.du_projet(projet)
    copie = _copie_privee(e, nouvel, lg)
    fichier = mem.fichiers[e.fichier]
    # Une décision et un sujet du backlog ont chacun leur fichier : il se
    # copie en privé, et un fichier public garde l'identifiant.
    propre = {"ADR": ch.decisions, "B": ch.backlog}.get(e.type)
    if propre and e.fichier.startswith(propre + "/"):
        # Le dossier du fichier, pas celui de la couche : un sujet clos garde
        # sa place parmi les clos, en public comme en privé.
        couche, (dossier, nom) = memoire.TYPES[e.type], e.fichier.rsplit("/", 1)
        prive_rel = ch.dans_prive(f"{dossier}/{nouvel}{nom[len(ident):]}")
        outils.ecrire(racine / prive_rel, f"{langue.entete_fichier(couche, 'privee', lg)}\n{copie}\n")
        public_rel = f"{dossier}/{ident}-basculee.md"
        outils.ecrire(racine / public_rel, f"{langue.entete_fichier(couche, 'publique', lg)}\n{_pierre(e, jour, lg)}\n")
        (racine / e.fichier).unlink()
    else:
        prive_rel = ch.dans_prive(e.fichier)
        cible = racine / prive_rel
        if not cible.is_file():
            titre = fichier.texte.split("\n# ", 1)[1].split("\n", 1)[0] if "\n# " in fichier.texte else fichier.couche
            outils.ecrire(cible, f"{langue.entete_fichier(fichier.couche, 'privee', lg)}\n# {titre}\n")
        cible.write_text(cible.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + copie + "\n", encoding="utf-8")
        public_rel = e.fichier
        texte = (racine / e.fichier).read_text(encoding="utf-8")
        if e.texte not in texte:
            raise ValueError(trad("`{ident}` : son texte ne se retrouve pas tel quel dans {fichier}",
                                  ident=ident, fichier=e.fichier))
        (racine / e.fichier).write_text(texte.replace(e.texte, _pierre(e, jour, lg), 1), encoding="utf-8")
    res = [trad("{ident} → {nouvel} : son titre et son texte sont dans {prive_rel}",
                ident=ident, nouvel=nouvel, prive_rel=prive_rel),
           trad("en public, {public_rel} ne garde de {ident} que l'identifiant : les renvois restent valides",
                public_rel=public_rel, ident=ident),
           trad("l'historique public garde l'ancien texte : seule une réécriture de l'historique, publiée en "
                "écrasant la branche, l'efface ; c'est à l'humain de la faire : le lui dire"),
           trad("un nom qui doit rester privé partout s'ajoute à la liste des termes : `socle private term "
                "<terme>`")]
    if mode(projet) == "compagnon":
        res.append(trad("mode compagnon : commiter la copie dans le dépôt privé, puis `socle private lock`"))
    return res


def _copie_privee(e: memoire.Entree, nouvel: str, lg: str) -> str:
    """L'entrée sous son identifiant privé, qui cite celle qu'elle reprend."""
    lignes = e.texte.splitlines()
    lignes[0] = lignes[0].replace(e.id, nouvel, 1)
    j = 1
    while j < len(lignes) and not lignes[j].strip():
        j += 1
    if j < len(lignes) and lignes[j].lstrip().startswith(">"):
        while j + 1 < len(lignes) and lignes[j + 1].lstrip().startswith(">"):
            j += 1
        lignes[j] = lignes[j].rstrip() + " · " + langue.meta(lg, depuis=e.id)[2:]
    else:
        lignes[1:1] = ["", langue.meta(lg, depuis=e.id)]
    return "\n".join(lignes)


def _pierre(e: memoire.Entree, jour: str, lg: str) -> str:
    """Ce qui reste en public d'une entrée basculée."""
    return (f"{'#' * e.niveau} {e.id} — {langue.mot(langue.TEXTES, 'titre-basculee', lg)}\n\n"
            f"{langue.meta(lg, basculee=jour)}\n\n{langue.mot(langue.TEXTES, 'texte-basculee', lg)}")
