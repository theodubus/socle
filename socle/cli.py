"""Ligne de commande du socle : `python3 .socle/socle <commande>`.

Les commandes portent des noms anglais (identifiants), leurs messages sont en
français. Toute commande de contrôle rend un code de sortie : 0 si tout passe.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

from socle import VERSION, config, hooks, language as langue, messages, utils as outils
from socle.messages import a_traduire, trad


def _projet(args) -> config.Projet:
    """Le projet ; ses messages, dès lors, dans la langue de sa mémoire."""
    projet = config.Projet.charger(Path(args.root) if getattr(args, "root", None) else None)
    messages.choisir(langue.du_projet(projet))
    return projet


def _base(projet: config.Projet, valeur: str | None) -> str | None:
    """La base demandée, ou le point de divergence avec la branche par défaut.
    Une base nulle (`0000…`, premier push d'une branche) retombe sur celui-ci."""
    if valeur and set(valeur) != {"0"} and outils.rev_existe(projet.racine, valeur):
        return outils.resoudre(projet.racine, valeur)
    if valeur and set(valeur) != {"0"}:
        print(trad("!! base « {valeur} » introuvable — repli sur la branche par défaut", valeur=valeur), file=sys.stderr)
    return outils.base_de_travail(projet.racine)


# --------------------------------------------------------------------------


def cmd_state(args) -> int:
    from socle import state as etat

    print(etat.calculer(_projet(args), contenus=not args.short))
    return 0


def cmd_check(args) -> int:
    from socle import context as contexte

    projet = _projet(args)
    base = _base(projet, args.base)
    ctx = contexte.Contexte(projet, etage=args.stage, base=base, tete=args.rev, rapide=args.fast)
    ids = [i.strip() for i in args.only.split(",")] if args.only else None
    rapport = contexte.executer(ctx, ids)
    titre = trad("socle {version} — contrôles, étage {etage}", version=VERSION, etage=args.stage) + (
        f", base {base[:10]}" if base else trad(", sans base"))
    rapport.afficher(titre, court=getattr(args, "court", False))
    return 0 if rapport.reussi else 1


def cmd_verify(args) -> int:
    from socle import context as contexte, verification
    from socle.report import Rapport

    projet = _projet(args)
    base = _base(projet, args.base)
    rapport = Rapport()
    if args.fast:
        verification.etapes_rapides(projet, rapport, flux=sys.stderr, refaire=args.refaire)
    else:
        verification.executer_etapes(projet, False, rapport, flux=sys.stderr)
    etage = "git" if args.fast else "ci"
    rapport.fusionner(contexte.executer(contexte.Contexte(projet, etage=etage, base=base, rapide=args.fast)))
    titre = (trad("socle {version} — vérification rapide", version=VERSION) if args.fast
             else trad("socle {version} — vérification complète", version=VERSION))
    rapport.afficher(titre + (f", base {base[:10]}" if base else ""))
    return 0 if rapport.reussi else 1


def cmd_ci(args) -> int:
    from socle import selftest as autotest, context as contexte, verification
    from socle.report import Rapport

    projet = _projet(args)
    base = _base(projet, args.base)
    rapport = Rapport()
    # L'auto-test tourne une fois, ici, pas aussi dans la suite de tests du
    # projet qui le contient : il y coûterait une seconde fois.
    if not args.no_selftest:
        os.environ[autotest.ENSUITE] = "1"
    try:
        verification.executer_etapes(projet, False, rapport, flux=sys.stderr)
    finally:
        os.environ.pop(autotest.ENSUITE, None)
    rapport.fusionner(contexte.executer(contexte.Contexte(projet, etage="ci", base=base)))
    if not args.no_selftest:
        rapport.fusionner(autotest.executer(projet, bavard=False))
    rapport.afficher(f"socle {VERSION} — CI" + (f", base {base[:10]}" if base else trad(", sans base")))
    return 0 if rapport.reussi else 1


def cmd_hook(args) -> int:
    from socle import hooks

    projet = _projet(args)
    evt = args.event
    if evt.startswith("git-"):
        outils.isoler_du_hook(projet.racine)
    if evt == "session-start":
        return hooks.session_start(projet, hooks.lire_entree())
    if evt == "pre-tool-use":
        return hooks.pre_tool_use(projet, hooks.lire_entree())
    if evt == "stop":
        return hooks.stop(projet, hooks.lire_entree())
    if evt == "git-pre-commit":
        return hooks.git_pre_commit(projet)
    if evt == "git-prepare-commit-msg":
        return hooks.git_prepare_commit_msg(projet, *args.rest[:2])
    if evt == "git-pre-push":
        return hooks.git_pre_push(projet)
    if evt == "git-commit-msg":
        return hooks.git_commit_msg(projet, *args.rest[:1])
    print(trad("hook inconnu : {evt}", evt=evt), file=sys.stderr)
    return 2


def cmd_next_id(args) -> int:
    from socle import memory as memoire

    projet = _projet(args)
    mem = memoire.Memoire.charger(projet.racine)
    type_ = TYPES_CLI[args.type]
    print(mem.prochain_id(type_, prive=args.private, date=date.today().isoformat()))
    return 0


TYPES_CLI = {"fact": "F", "backlog": "B", "adr": "ADR", "journal": "J", "request": "D"}


def cmd_new(args) -> int:
    from socle import memory as memoire, private as zone_privee

    projet = _projet(args)
    racine = projet.racine
    mem = memoire.Memoire.charger(racine)
    type_ = TYPES_CLI[args.type]
    jour = date.today().isoformat()
    questions = getattr(args, "questions", False)
    if questions and type_ != "D":
        print(trad("`--questions` ne vaut que pour une demande (`request`)"), file=sys.stderr)
        return 2
    # Avec une mémoire privée, le contenu nouveau est privé par défaut
    # (cadrage, règles de classement, point 3), couche par couche selon la
    # politique (`[private] layers`). Une demande ne devient privée que
    # si l'humain l'a choisi : il doit pouvoir la lire là où il lit. Une
    # consigne de l'humain sur une entrée précise se dit par `--private` ou
    # `--public`.
    for nom in zone_privee.couches_inconnues(projet):
        print(trad("`[private] layers` : « {nom} » n'est pas une couche ({liste})",
                   nom=nom, liste=', '.join(zone_privee.COUCHES_PRIVABLES)), file=sys.stderr)
    defaut = memoire.TYPES[type_] in zone_privee.couches_privees(projet)
    prive = getattr(args, "private", False) or (defaut and not getattr(args, "public", False))
    acces = zone_privee.acces(projet, mem.illisibles) if prive else None
    if acces is not None and not acces.disponible:
        # Sans elle, l'identifiant se devinerait, et le texte clair
        # s'accolerait à un fichier chiffré.
        print(trad("refus : mémoire privée indisponible ({raison}) ; une entrée privée ne s'écrit pas à "
                   "l'aveugle. `--public` si elle peut être publique, sinon attendre l'accès.",
                   raison=acces.raison), file=sys.stderr)
        return 2
    from socle import identifiers as identifiants

    # Ceux que les branches distantes ont déjà pris aussi.
    ident = mem.prochain_id(type_, prive=prive, date=jour, pris_ailleurs=identifiants.pris_ailleurs(racine, type_))
    titre = args.title
    zone = "privee" if prive else "publique"
    ch = projet.chemins
    lieu = (lambda c: racine / ch.dans_prive(c)) if prive else (lambda c: racine / c)
    # La langue de la mémoire du projet : les mots-clés et les
    # gabarits s'écrivent dans la sienne.
    lg = langue.du_projet(projet)
    squelette = langue.SQUELETTES[lg].get(type_, "")
    # Ce qui s'affiche avant l'identifiant, imprimé une fois l'entrée
    # écrite : une sortie coupée (`| head -1`) ne l'empêche plus.
    index = ""
    if type_ == "F":
        chemin = lieu(ch.canonique)
        _ajouter(chemin, f"\n## {ident} — {titre}\n\n{squelette}\n", langue.entete_fichier("canonique", zone, lg))
    elif type_ == "B":
        # Le backlog s'affiche avec le sujet ajouté : un doublon se voit ici.
        index = _texte_index(mem, "backlog")
        bloc = squelette.format(lu=memoire.empreinte_index(mem, "backlog"))
        # Un fichier par sujet, comme une décision.
        chemin = lieu(ch.backlog) / f"{ident}-{memoire.nom_de_fichier(titre)}.md"
        outils.ecrire(chemin, f"{langue.entete_fichier('backlog', zone, lg)}\n# {ident} — {titre}\n\n{bloc}\n")
    elif type_ == "J":
        bloc = f"\n## {ident} — {titre}\n\n{squelette}\n"
        dossier = lieu(ch.journal)
        # Le squelette grandira : de la marge, pour que l'entrée remplie tienne.
        chemin = memoire.fichier_journal(dossier, jour[:7], projet.budget_octets(f"{ch.journal}/{jour[:7]}.md"),
                                         len(bloc.encode("utf-8")) + 2000)
        if not chemin.is_file():
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(f"{langue.entete_fichier('journal', zone, lg)}\n"
                              f"# {langue.mot(langue.TEXTES, 'titre-journal', lg)} — {jour[:7]}\n", encoding="utf-8")
        _ajouter(chemin, bloc)
    elif type_ == "ADR":
        # Les décisions s'affichent avec celle qu'on ajoute : on ne rouvre pas
        # une décision prise sans fait nouveau.
        index = _texte_index(mem, "decisions")
        chemin = lieu(ch.decisions) / f"{ident}-{memoire.nom_de_fichier(titre)}.md"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        bloc = squelette.format(date=jour, lu=memoire.empreinte_index(mem, "decisions"))
        chemin.write_text(f"{langue.entete_fichier('decisions', zone, lg)}\n# {ident} — {titre}\n\n{bloc}\n",
                          encoding="utf-8")
    else:
        from socle.templates import gabarit

        chemin = lieu(ch.demandes) / f"{ident}-{memoire.nom_de_fichier(titre)}.md"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        # Des questions de cadrage (D-0067) : ouvertes, sur le modèle des
        # questions de départ, quand l'intention de l'humain manque.
        texte = gabarit("questions.md" if questions else "request.md", lg).format(id=ident, titre=titre, date=jour)
        entete = texte.split("\n", 1)[0]
        chemin.write_text(texte.replace(entete, langue.entete_fichier("demandes", zone, lg), 1), encoding="utf-8")
    if index:
        print(index)
    print(f"{ident}\t{chemin.relative_to(racine)}")
    if type_ == "D":
        # Le contrat, avant qu'elle soit écrite et non au refus du lint ;
        # après l'identifiant, que la première ligne garde (ADR-0058).
        from socle import requests as demandes

        print(demandes.contrat(projet, str(Path(ch.demandes) / chemin.name), questions=questions))
    return 0


def _ajouter(chemin: Path, bloc: str, entete: str | None = None):
    """Ajoute une entrée au fichier ; un fichier neuf reçoit d'abord son
    en-tête."""
    if chemin.is_file():
        texte = chemin.read_text(encoding="utf-8")
    else:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        texte = f"{entete}\n" if entete else ""
    chemin.write_text(texte.rstrip("\n") + "\n" + bloc, encoding="utf-8")


def cmd_show(args) -> int:
    """Une entrée de mémoire par son identifiant, où qu'elle soit (archivée
    comprise) ; pour une demande, sa réponse aussi."""
    from socle import requests as demandes, memory as memoire

    projet = _projet(args)
    mem = memoire.Memoire.charger(projet.racine)
    code = 0
    if args.index:
        _afficher_index(mem, args.index)
    for ident in args.ids:
        e = mem.entree(ident)
        if e is None:
            print(trad("{ident} : aucune entrée de ce nom dans la mémoire", ident=ident), file=sys.stderr)
            code = 1
            continue
        lieu = f"{e.fichier}:{e.ligne}" + (trad(", archivée dans {parent}", parent=e.parent) if e.parent else "")
        # L'empreinte s'imprime avec le texte : la citer (`ID@empreinte`)
        # montre qu'on a lu cette version-là.
        print(f"--- {ident}@{memoire.empreinte_entree(e)} ({lieu}) ---")
        print(e.texte)
        if e.type == "D":
            d = next((d for d in demandes.toutes(projet.racine) if d.id == ident), None)
            if d and d.chemin_reponse:
                print(trad("\n--- réponse ({chemin}) : {statut} ---", chemin=d.chemin_reponse, statut=d.statut_affiche))
                print((projet.racine / d.chemin_reponse).read_text(encoding="utf-8").rstrip())
            elif d:
                print(f"\n--- {d.statut_affiche} ---")
    return code


def cmd_prive(args) -> int:
    """La mémoire privée : état, termes, bascule d'une entrée, dépôt compagnon et son verrou."""
    from socle import private as prive

    projet = _projet(args)
    racine = projet.racine
    if args.action == "status":
        print(prive.ligne_etat(projet))
        return 0
    if args.action == "term":
        if prive.mode(projet) is None or not args.terme:
            print(trad("`socle private term <terme>` : une mémoire privée, et un terme"), file=sys.stderr)
            return 1
        try:
            ajoute = prive.ajouter_terme(projet, " ".join(args.terme))
        except RuntimeError as e:
            print(f"refus : {e}", file=sys.stderr)
            return 2
        print(trad("terme ajouté à la liste privée") if ajoute else trad("terme déjà dans la liste privée"))
        return 0
    if args.action == "install":
        if hooks.sous_un_agent("`socle private install`"):
            return 2
        if not args.repo:
            print("`socle private install --repo <adresse du dépôt privé>`", file=sys.stderr)
            return 1
        from socle import private_setup as prive_installation

        code, lignes = prive_installation.installer_compagnon(projet, args.repo)
        print("\n".join(lignes), file=sys.stderr if code else sys.stdout)
        return code
    if args.action == "move":
        if len(args.terme) != 1:
            print(trad("`socle private move <ID>` : l'identifiant d'une entrée publique"), file=sys.stderr)
            return 1
        try:
            from socle import move as bascule

            lignes = bascule.basculer(projet, args.terme[0], date.today().isoformat())
        except ValueError as e:
            print(f"refus : {e}", file=sys.stderr)
            return 1
        print("\n".join(lignes))
        return 0
    if prive.mode(projet) != "compagnon":
        print(trad("le verrou n'existe qu'en mode compagnon (`[private] mode` de la politique)"), file=sys.stderr)
        return 1
    if args.action == "recover":
        return prive.recuperer(projet)
    sha = prive.commit_compagnon(racine)
    if sha is None:
        print(trad("dépôt privé absent de `{dossier}/` : le cloner d'abord",
                   dossier=prive.dossier(projet.racine)), file=sys.stderr)
        return 1
    if args.action == "lock":
        modifies = prive.compagnon_modifie(racine)
        if modifies:
            print(trad("{n} changement(s) privé(s) sans commit : les commiter dans le dépôt privé d'abord",
                       n=len(modifies)),
                  file=sys.stderr)
            return 1
        prive.ecrire_verrou(racine, sha)
        print(trad("verrou : {sha} — à commiter avec le reste (`{fichier_verrou}`)",
                   sha=sha[:10], fichier_verrou=prive.fichier_verrou(projet.racine)))
        return 0
    verrou = prive.lire_verrou(racine)
    if verrou is None:
        print(trad("pas de verrou à extraire"), file=sys.stderr)
        return 1
    outils.git(prive.depot_compagnon(racine), "checkout", "-q", "--detach", verrou)
    print(trad("mémoire privée remise au verrou : {verrou}", verrou=verrou[:10]))
    return 0


def cmd_relu(args) -> int:
    """L'humain a relu ce qui part vers le dépôt public : il le dit
    lui-même, ou l'agent relaie son accord donné dans la conversation, avec
    son texte exact."""
    from socle import private as prive

    projet = _projet(args)
    if not args.relayed and hooks.sous_un_agent(trad("dire relu sans --relayed")):
        return 2
    citation = Path(args.quote_file).read_text(encoding="utf-8") if args.quote_file else (args.quote or "")
    par = _signataire(projet, args)
    if args.relayed and (not par or len(citation.strip()) < 2):
        print(trad("refus : une relecture relayée nomme l'humain (--by) et cite son texte exact (--quote-file)"),
              file=sys.stderr)
        return 2
    sha = outils.git(projet.racine, "rev-parse", args.rev).strip()
    prive.noter_relecture(projet.racine, sha, par,
                          "conversation" if args.relayed else "terminal", citation)
    print(trad("relu : {sha} peut partir vers le dépôt public", sha=sha[:10]))
    return 0


def cmd_url(args) -> int:
    """Le permalien d'un fichier ou d'une entrée, à donner à l'humain : il
    lit sur GitHub, pas dans le conteneur de l'agent."""
    from socle import links as liens

    projet = _projet(args)
    code = 0
    for cible in args.cibles:
        url, avertissement = liens.lien(projet, cible)
        if avertissement:
            print(f"{cible} : {avertissement}", file=sys.stderr)
        if url is None:
            code = 1
            continue
        print(f"[{cible}]({url})")
    return code


def cmd_review(args) -> int:
    """Le dossier de la revue adversariale d'un lot (ADR-0042) : ce que
    reçoit le relecteur, qui n'a pas la conversation. Avec `--request`, celui
    de la relecture à froid d'une demande (ADR-0046). Le moteur ne lance pas
    le lecteur : les skills `socle-review` et `socle-request` disent comment."""
    from socle import review as revue

    demande = getattr(args, "request", None)
    if demande:
        texte = revue.dossier_demande(_projet(args), demande)
        if texte is None:
            print(trad("aucune demande {id}", id=demande), file=sys.stderr)
            return 2
        print(texte, end="")
        return 0
    print(revue.dossier(_projet(args), args.base, args.max_bytes), end="")
    return 0


def _texte_index(mem, index: str) -> str:
    from socle import memory as memoire

    lignes = memoire.lignes_index(mem, index)
    return "\n".join([trad("--- index {index}@{empreinte} — à citer `lu : {index}@…` ---", index=index,
                            empreinte=memoire.empreinte_index(mem, index)),
                      "\n".join(lignes) if lignes else trad("(vide)")])


def _afficher_index(mem, index: str):
    print(_texte_index(mem, index))


def cmd_answer(args) -> int:
    """L'humain répond lui-même, ou l'agent relaie (`--relayed`) une réponse
    donnée dans la conversation, en citant son texte exact."""
    from socle import requests as demandes

    projet = _projet(args)
    cible = [d for d in demandes.toutes(projet.racine) if d.id == args.request]
    if not cible:
        print(trad("demande introuvable : {demande}", demande=args.request), file=sys.stderr)
        return 2
    d = cible[0]
    citation = args.quote or ""
    if args.quote_file:
        citation = Path(args.quote_file).read_text(encoding="utf-8")
    par = _signataire(projet, args)
    if args.relayed and not par:
        print(trad(REFUS_SANS_NOM), file=sys.stderr)
        return 2
    if not args.relayed and hooks.sous_un_agent(trad("répondre sans --relayed")):
        return 2
    if args.relayed:
        pourquoi = demande_illisible(projet, d)
        if pourquoi:
            print(trad("refus : {id} n'a pas pu être lue par l'humain — {pourquoi}. Une réponse ne se relaie "
                       "qu'à une demande qu'il a pu lire : la pousser, lui donner son lien (`socle url {id}`), "
                       "puis consigner la réponse qu'il donne ensuite. Il peut aussi répondre lui-même, sans "
                       "--relayed, dans son terminal.", id=d.id, pourquoi=pourquoi), file=sys.stderr)
            return 2
    if not args.relayed:
        print(d.texte)
        print("\n" + "=" * 72)
    try:
        chemin = demandes.ecrire_reponse(projet.racine, d, args.answer, args.text or "", par,
                                         date.today().isoformat(),
                                         canal="conversation" if args.relayed else "terminal", citation=citation)
    except ValueError as e:
        print(f"refus : {e}", file=sys.stderr)
        return 2
    print(trad("réponse « {answer} » écrite dans {chemin} — à commiter avec la suite.",
               answer=args.answer, chemin=chemin))
    return 0


def cmd_decision(args) -> int:
    """Une décision prise en séance : l'humain a lu la question
    dans la conversation et y a répondu ; l'agent la consigne avec sa réponse
    mot pour mot (`--relayed`), ou l'humain le fait lui-même. `--about` nomme
    ce qu'elle approuve."""
    from socle import requests as demandes

    projet = _projet(args)
    citation = args.quote or ""
    if args.quote_file:
        citation = Path(args.quote_file).read_text(encoding="utf-8")
    par = _signataire(projet, args)
    if args.relayed and not par:
        print(trad(REFUS_SANS_NOM), file=sys.stderr)
        return 2
    if not args.relayed and hooks.sous_un_agent(trad("consigner une décision sans --relayed")):
        return 2
    sujet = ""
    if args.about:
        chemin = args.about
        texte = outils.lire_a(projet.racine, None, chemin)
        if texte is None:
            print(trad("refus : « {chemin} » n'existe pas dans le dépôt", chemin=chemin), file=sys.stderr)
            return 2
        sujet = chemin
    question = Path(args.question_file).read_text(encoding="utf-8") if args.question_file else ""
    try:
        chemin, reponse = demandes.ecrire_seance(projet, args.question, question, args.answer,
                                                 par, date.today().isoformat(),
                                                 "conversation" if args.relayed else "terminal", citation, sujet)
    except ValueError as e:
        print(trad("refus : {erreur}", erreur=e), file=sys.stderr)
        return 2
    print(trad("décision en séance consignée : {chemin}, et sa réponse « {answer} » — à commiter avec la suite.",
               chemin=chemin, answer=args.answer))
    return 0


def demande_illisible(projet, d) -> str | None:
    """Pourquoi l'humain n'a pas pu lire la demande telle qu'elle est,
    ou `None` : `demandes.illisible`."""
    from socle import requests as demandes

    return demandes.illisible(projet, d)


def fichiers_a_approuver(projet) -> list[str]:
    """Les fichiers protégés changés depuis le dernier commit, que rien ne
    valide encore : ceux que `socle approve` approuverait."""
    from socle import context as contexte
    from socle.checks_ratchet import proteges
    from socle.report import Rapport

    if not outils.a_des_commits(projet.racine):
        return []
    r = Rapport()
    proteges(contexte.Contexte(projet, etage="agent", base="HEAD"), r)
    return sorted({c.chemin for c in r.erreurs("protege.fichiers") if c.chemin})


def _auteur(projet) -> str:
    """L'humain : son nom dans la politique, sinon celui de git."""
    return (str(projet.pol("human", "name", defaut="") or "").strip()
            or outils.git(projet.racine, "config", "user.name", check=False).strip() or "humain")


def _signataire(projet, args) -> str | None:
    """Qui signe une réponse : `--by`, sinon le nom que la politique donne à
    l'humain. Relayée sans l'un ni l'autre, personne : l'agent ne
    devine pas un nom. Un `--by` qui diffère de la politique est dit."""
    nom = str(projet.pol("human", "name", defaut="") or "").strip()
    if args.by and nom and args.by.strip() != nom:
        print(trad("note : --by « {by} » n'est pas le nom que la politique donne à l'humain (« {nom} »)",
                   by=args.by, nom=nom), file=sys.stderr)
    return args.by or nom or (None if args.relayed else _auteur(projet))


REFUS_SANS_NOM = a_traduire("refus : une réponse relayée nomme l'humain qui l'a donnée (--by), à moins que la "
                            "politique ne le nomme (`[human] name`)")


def cmd_approve(args) -> int:
    """Réservé à l'humain : valide d'un coup un changement qu'il fait lui-même
    (fichier protégé, clé de garde-fou), en écrivant la demande et sa réponse."""
    from socle import requests as demandes, fingerprint as empreinte, memory as memoire
    from socle.templates import gabarit

    if hooks.sous_un_agent("`socle approve`"):
        return 2
    projet = _projet(args)
    racine = projet.racine
    if not args.files and not getattr(args, "keys", None):
        # Sans liste : les fichiers protégés que l'humain vient de changer,
        # montrés avant d'être approuvés.
        args.files = fichiers_a_approuver(projet)
        if not args.files:
            print(trad("rien à approuver : aucun fichier protégé changé depuis le dernier commit"))
            return 0
        print(trad("{n} fichier(s) protégé(s) changé(s) depuis le dernier commit :", n=len(args.files)))
        for f in args.files:
            print(f"  - {f}")
        if not getattr(args, "oui", False):
            if not sys.stdin.isatty():
                print(trad("refus : confirmer par `--yes`, ou nommer les fichiers par `--files`"), file=sys.stderr)
                return 2
            if input(trad("Les approuver ? [o/N] ")).strip().lower() not in ("o", "oui", "y", "yes"):
                print(trad("rien n'est approuvé"))
                return 1
    mem = memoire.Memoire.charger(racine)
    ident = mem.prochain_id("D")
    jour = date.today().isoformat()
    # La raison peut citer des entrées : elles se citent avec leur empreinte,
    # comme dans toute demande nouvelle. Une entrée qui n'existe
    # pas ici, ou un fichier qui n'existe ni ici ni au dernier commit, arrête
    # tout avant d'écrire.
    inconnus = []

    def citer(m) -> str:
        e = mem.entree(m.group(0)) if memoire.decouper_id(m.group(0)) else None
        if e is None:
            inconnus.append(m.group(0))
            return m.group(0)
        return f"{m.group(0)}@{memoire.empreinte_entree(e)}"

    raison = re.sub(memoire.ID_RE.pattern + r"(?!@)", citer, args.text)
    absents = [f for f in args.files or [] if not (racine / f).is_file()
               and not outils.git_reussit(racine, "cat-file", "-e", f"HEAD:{f}")]
    if inconnus or absents:
        for i in inconnus:
            print(trad("refus : la raison cite {i}, qui n'existe pas dans cette mémoire", i=i), file=sys.stderr)
        for f in absents:
            print(trad("refus : {f} n'existe ni ici ni au dernier commit : rien à approuver", f=f), file=sys.stderr)
        return 2
    lg = langue.du_projet(projet)
    en = lg == "en"
    cites = []
    for f in args.files or []:
        p = racine / f
        nouvelle = empreinte.courte(empreinte.fichier(p)) if p.is_file() else empreinte.supprime(lg)
        cites.append(f"- `{f}` — protected file changed by the human themselves; new fingerprint `{nouvelle}`."
                     if en else f"- `{f}` — fichier protégé modifié par l'humain lui-même ; empreinte nouvelle "
                     f"`{nouvelle}`.")
    for k in args.keys or []:
        cites.append(f"- `{k}` — guardrail key loosened by the human themselves, knowingly." if en else
                     f"- `{k}` — clé des garde-fous assouplie par l'humain lui-même, en connaissance de cause.")
    if not cites:
        print(trad("rien à approuver : --files ou --keys"), file=sys.stderr)
        return 2
    texte = gabarit("approval.md", lg).format(id=ident, date=jour, raison=raison, elements="\n".join(cites),
                                                 moteur=projet.dossier_moteur)
    chemin = racine / projet.chemins.demandes / f"{ident}-approbation-humaine.md"
    chemin.write_text(texte, encoding="utf-8")
    d = demandes.charger(racine, None, str(chemin.relative_to(racine)), texte)
    demandes.ecrire_reponse(racine, d, langue.mot(langue.REPONSES, "valider", lg), args.text, _auteur(projet), jour)
    print(trad("{ident} écrite et validée : {chemin}", ident=ident, chemin=chemin.relative_to(racine)))
    return 0


def cmd_install(args) -> int:
    from socle import installer as installeur

    return installeur.installer(
        cible=Path(args.target).resolve(),
        adaptateur=args.adapter or "auto",
        proprietaire=args.owner,
        adoption=args.adoption,
        mode=args.mode,
        source=Path(__file__).resolve().parent.parent,
        prive=args.private,
        relecture=args.review,
        demandes_privees=args.private_requests,
        filtre=args.filter,
        langue_memoire=getattr(args, "language", None),
        plafonds=Path(args.mutation_caps).resolve() if getattr(args, "mutation_caps", None) else None,
        humain=getattr(args, "human", None) or "",
    )


def cmd_init(args) -> int:
    """L'initialisation : un document de cadrage, rien, un dépôt existant, ou
    le document et le dépôt ensemble."""
    from socle import initialization as initialisation

    projet = _projet(args)
    return initialisation.initialiser(projet, Path(args.cadrage).resolve() if args.cadrage else None, args.depot)


def cmd_selftest(args) -> int:
    from socle import selftest as autotest

    rapport = autotest.executer(_projet(args), bavard=args.verbose)
    rapport.afficher(trad("socle {version} — auto-test par injection de défauts", version=VERSION))
    return 0 if rapport.reussi else 1


def cmd_fingerprint(args) -> int:
    from socle import fingerprint as empreinte

    projet = _projet(args)
    calculee, n = empreinte.calculer(projet.racine, projet.dossier_moteur)
    print(trad("{calculee}  ({n} fichiers sous {dossier_moteur}/socle et le lanceur)",
               calculee=calculee, n=n, dossier_moteur=projet.dossier_moteur))
    for f in args.files or []:
        p = projet.racine / f
        print(f"{empreinte.courte(empreinte.fichier(p)) if p.is_file() else trad('supprimé')}  {f}")
    return 0


def cmd_mutation_verdict(args) -> int:
    from socle import mutation

    projet = _projet(args)
    if getattr(args, "adaptateur", None):
        a = next((a for a in projet.adaptateurs if a.nom == args.adaptateur), None)
        if a is None:
            print(trad("adaptateur inconnu : « {nom} » (ceux du projet : {liste})", nom=args.adaptateur,
                       liste=", ".join(a.nom for a in projet.adaptateurs)), file=sys.stderr)
            return 2
        projet = projet.pour(a)
    rapport = mutation.verdict(projet, Path(args.results), poser=getattr(args, "poser", False))
    rapport.afficher(trad("socle {version} — verdict de mutation", version=VERSION))
    return 0 if rapport.reussi else 1


def cmd_mutation_run(args) -> int:
    from socle import mutation

    rapport = mutation.balayer(_projet(args), poser=getattr(args, "poser", False))
    rapport.afficher(trad("socle {version} — balayage de mutation", version=VERSION))
    return 0 if rapport.reussi else 1


def cmd_renumber(args) -> int:
    from socle import identifiers as identifiants

    try:
        lignes = identifiants.renumeroter(_projet(args), args.id)
    except ValueError as e:
        print(f"refus : {e}", file=sys.stderr)
        return 1
    print("\n".join(lignes))
    return 0


def cmd_archive(args) -> int:
    from socle import archive as archivage

    return archivage.archiver_backlog(_projet(args))


def cmd_checks(args) -> int:
    from socle import context as contexte

    for c in contexte.charger_controles().values():
        premiere = trad(contexte.resume(c.doc)) if c.doc else ""
        print(f"{c.id:<28} {','.join(c.etages):<12} {'base ' if c.base else '     '}{'lent ' if c.lent else '     '}{premiere}")
    return 0


# Les commandes par public : l'humain en a peu, l'agent
# davantage, le reste sert aux hooks, à la CI et au moteur lui-même.
GROUPES = {
    a_traduire("pour l'humain"): ["help", "install", "init", "state", "answer", "decision", "approve", "reviewed",
                                  "private install"],
    a_traduire("pour l'agent"): ["new", "show", "url", "review", "verify", "check", "next-id", "private",
                                 "mutation-verdict", "mutation-run", "renumber", "archive", "checks"],
    a_traduire("internes (hooks, CI, moteur)"): ["hook", "ci", "selftest", "fingerprint"],
}


# Une sous-commande que l'aide range à part de sa commande.
SOUS_COMMANDES = {"private install": a_traduire("(humain seul) mettre en place le dépôt privé du mode "
                                                "compagnon : --repo <adresse>")}


def aide_groupee(aides: dict[str, str], groupes: list[str] | None = None) -> str:
    """Les commandes rangées par public, une ligne chacune."""
    lignes = []
    for groupe, noms in GROUPES.items():
        if groupes is not None and groupe not in groupes:
            continue
        lignes.append(trad("{groupe} :", groupe=trad(groupe)))
        lignes += [f"  {n:<17} {aides.get(n) or trad(SOUS_COMMANDES.get(n, ''))}" for n in noms]
        lignes.append("")
    return "\n".join(lignes).rstrip()


def cmd_aide(args) -> int:
    """Le guide de l'humain, dans la langue de la mémoire du projet quand il
    en a une version (`HELP.en.md`)."""
    dossier = Path(__file__).resolve().parent
    traduit = dossier / f"HELP.{messages.langue()}.md"
    print((traduit if traduit.is_file() else dossier / "HELP.md").read_text(encoding="utf-8").rstrip())
    return 0


def analyseur() -> tuple[argparse.ArgumentParser, dict[str, str]]:
    """L'analyseur de la ligne de commande, et l'aide d'une ligne de chaque
    commande."""
    p = argparse.ArgumentParser(prog="socle", description=trad("socle {version} — mémoire, documentation et "
                                                               "tests fiables", version=VERSION),
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", help=trad("racine du projet (défaut : le dépôt git courant)"))
    sp = p.add_subparsers(dest="cmd", required=True, metavar="<commande>")

    s = sp.add_parser("help", help=trad("le guide de l'humain : ses gestes, chacun avec sa commande"))
    s.set_defaults(f=cmd_aide)

    s = sp.add_parser("state", help=trad("où en est le projet, calculé à chaque fois (injecté au démarrage de "
                                         "l'agent)"))
    s.add_argument("--short", action="store_true", help=trad("sans le contenu de l'actif et du canonique"))
    s.set_defaults(f=cmd_state)

    s = sp.add_parser("check", help=trad("contrôles du socle, un code de sortie"))
    s.add_argument("--stage", choices=("agent", "git", "ci"), default="ci")
    s.add_argument("--base", help=trad("révision de base (défaut : divergence avec la branche par défaut)"))
    s.add_argument("--rev", help=trad("révision contrôlée (défaut : l'arbre de travail)"))
    s.add_argument("--only", help=trad("liste de contrôles, séparés par des virgules"))
    s.add_argument("--fast", action="store_true", help=trad("sans les contrôles lents"))
    s.add_argument("--short", action="store_true", dest="court", help=trad("ne montrer que ce qui échoue ou "
                                                                           "avertit"))
    s.set_defaults(f=cmd_check)

    s = sp.add_parser("verify", help=trad("le contrat verify : capacités de l'adaptateur puis contrôles"))
    s.add_argument("--fast", action="store_true", dest="fast")
    s.add_argument("--redo", action="store_true", dest="refaire",
                   help=trad("relancer les étapes rapides même si elles ont déjà passé sur cet arbre exact"))
    s.add_argument("--base")
    s.set_defaults(f=cmd_verify)

    s = sp.add_parser("ci", help=trad("tout : capacités, contrôles, auto-test"))
    s.add_argument("--base")
    s.add_argument("--no-selftest", action="store_true")
    s.set_defaults(f=cmd_ci)

    s = sp.add_parser("hook", help=trad("point d'entrée des hooks de l'agent et de git"))
    s.add_argument("event")
    s.add_argument("rest", nargs="*")
    s.set_defaults(f=cmd_hook)

    s = sp.add_parser("next-id", help=trad("prochain identifiant libre"))
    s.add_argument("type", choices=sorted(TYPES_CLI))
    s.add_argument("--private", action="store_true")
    s.set_defaults(f=cmd_next_id)

    s = sp.add_parser("new", help=trad("ajoute une entrée squelette avec son identifiant"))
    s.add_argument("type", choices=sorted(TYPES_CLI))
    s.add_argument("title")
    s.add_argument("--questions", action="store_true",
                   help=trad("avec `request` : des questions de cadrage d'un sujet, ouvertes, auxquelles l'humain "
                             "répond librement"))
    zone = s.add_mutually_exclusive_group()
    zone.add_argument("--private", action="store_true", help=trad("dans la mémoire privée (défaut quand elle "
                                                                  "existe)"))
    zone.add_argument("--public", action="store_true", help=trad("dans la mémoire publique, même quand une "
                                                                 "mémoire privée existe"))
    s.set_defaults(f=cmd_new)

    s = sp.add_parser("show", help=trad("afficher une entrée de mémoire, avec son empreinte, ou un index"))
    s.add_argument("ids", nargs="*")
    s.add_argument("--index", choices=("decisions", "backlog"), help=trad("l'index des décisions ou du backlog "
                                                                          "ouvert"))
    s.set_defaults(f=cmd_show)

    s = sp.add_parser("private", help=trad("mémoire privée : état, verrou du dépôt compagnon, termes, bascule "
                                           "; `install` (humain seul) met en place le dépôt compagnon"))
    s.add_argument("action", choices=("status", "install", "lock", "extract", "recover", "term", "move"))
    s.add_argument("terme", nargs="*", help=trad("avec `term` : le terme à ajouter à la liste privée ; avec "
                                                 "`move` : l'identifiant de l'entrée publique à basculer dans "
                                                 "la mémoire privée"))
    s.add_argument("--repo", help=trad("avec `install` (humain seul) : l'adresse du dépôt privé, cloné et mis "
                                       "en place"))
    s.set_defaults(f=cmd_prive)

    s = sp.add_parser("reviewed", help=trad("tu as relu ce qui part vers le dépôt public ; l'agent y relaie "
                                            "ton accord (--relayed)"))
    s.add_argument("--rev", default="HEAD")
    s.add_argument("--by")
    s.add_argument("--relayed", action="store_true", help=trad("accord donné par l'humain dans la conversation"))
    s.add_argument("--quote")
    s.add_argument("--quote-file")
    s.set_defaults(f=cmd_relu)

    s = sp.add_parser("url", help=trad("le permalien d'un fichier ou d'une entrée, à donner à l'humain"))
    s.add_argument("cibles", nargs="+", metavar="chemin|ID")
    s.set_defaults(f=cmd_url)

    s = sp.add_parser("review", help=trad("le dossier de la revue adversariale d'un lot, pour un relecteur sans "
                                          "contexte"))
    s.add_argument("--base", help=trad("la base du lot (par défaut : la branche distante, sinon la branche par "
                                       "défaut)"))
    s.add_argument("--max-bytes", type=int, default=60_000, help=trad("le plafond du diff montré"))
    s.add_argument("--request", metavar="D-NNNN", help=trad("le dossier de la relecture à froid de cette demande, "
                                                            "pour un lecteur qui n'a que son texte"))
    s.set_defaults(f=cmd_review)

    s = sp.add_parser("answer", help=trad("répondre à une demande ; l'agent y relaie (--relayed) ta réponse "
                                          "donnée dans la conversation"))
    s.add_argument("request")
    s.add_argument("answer")
    s.add_argument("--text", default="")
    s.add_argument("--by")
    s.add_argument("--relayed", action="store_true", help=trad("réponse donnée par l'humain dans la "
                                                               "conversation"))
    s.add_argument("--quote", help=trad("texte exact de l'humain (avec --relayed)"))
    s.add_argument("--quote-file", help=trad("fichier qui contient le texte exact de l'humain"))
    s.set_defaults(f=cmd_answer)

    s = sp.add_parser("decision", help=trad("consigner une décision prise en séance, avec la réponse de l'humain ; "
                                            "l'agent y relaie (--relayed) ta réponse mot pour mot"))
    s.add_argument("question")
    s.add_argument("answer")
    s.add_argument("--question-file", help=trad("fichier qui contient la question telle que l'humain l'a lue"))
    s.add_argument("--about", help=trad("ce que la décision approuve (le chemin du document)"))
    s.add_argument("--by")
    s.add_argument("--relayed", action="store_true", help=trad("réponse donnée par l'humain dans la "
                                                               "conversation"))
    s.add_argument("--quote", help=trad("texte exact de l'humain (avec --relayed)"))
    s.add_argument("--quote-file", help=trad("fichier qui contient le texte exact de l'humain"))
    s.set_defaults(f=cmd_decision)

    s = sp.add_parser("approve", help=trad("(humain seul) approuver tes changements protégés ; sans --files, "
                                           "ceux qui ont changé"))
    s.add_argument("--files", nargs="*")
    s.add_argument("--keys", nargs="*")
    s.add_argument("--text", required=True)
    s.add_argument("--yes", action="store_true", dest="oui", help=trad("sans --files : approuver sans demander "
                                                                       "confirmation"))
    s.set_defaults(f=cmd_approve)

    s = sp.add_parser("install", help=trad("installer ou mettre à jour le socle dans un projet"))
    s.add_argument("--target", default=".")
    s.add_argument("--adapter", action="append",
                   help=trad("`auto`, le défaut (un par langage du dépôt), un adaptateur maintenu ({adaptateurs}) "
                             "ou le chemin d'un .toml ; répété, un par langage, le premier nommé étant le "
                             "principal", adaptateurs=", ".join(sorted(
                                 x.stem for x in (Path(__file__).resolve().parent / "adapters").glob("*.toml")))))
    s.add_argument("--owner", default="", help=trad("propriétaire pour CODEOWNERS, ex. @theodubus"))
    s.add_argument("--human", help=trad("le nom de l'humain, qui signe les réponses que l'agent relaie (défaut : son "
                                        "nom git, hors session cloud)"))
    s.add_argument("--adoption", action="store_true", help=trad("projet existant : plafonds au niveau actuel"))
    s.add_argument("--mode", choices=(config.MODE_PROJET, config.MODE_AMONT), default=config.MODE_PROJET)
    s.add_argument("--private", choices=("compagnon", "chiffre"), help=trad("mémoire privée, et son mode"))
    s.add_argument("--review", choices=("aucune", "chaque-push", "lots"), help=trad("relecture humaine avant publication"))
    s.add_argument("--private-requests", action="store_true", help=trad("demandes et réponses dans la mémoire "
                                                                        "privée"))
    s.add_argument("--filter", default="git-crypt", help=trad("mode chiffré : le nom du filtre git de l'outil"))
    s.add_argument("--language", choices=("fr", "en"),
                   help=trad("langue de la mémoire d'un projet neuf : mots-clés, gabarits et messages du moteur "
                             "(défaut : fr)"))
    s.add_argument("--mutation-caps", help=trad("des plafonds de mutation déjà mesurés, à reprendre au lieu de poser "
                                                "ces modules « à mesurer » : un fichier TOML de `[mutation.caps]`"))
    s.set_defaults(f=cmd_install)

    s = sp.add_parser("init", help=trad("initialiser la mémoire depuis un cadrage, rien, ou le dépôt existant"))
    s.add_argument("--brief", dest="cadrage", help=trad("le document de cadrage, archivé tel quel"))
    s.add_argument("--repo", action="store_true", dest="depot", help=trad("auditer le dépôt existant, en lecture "
                                                                          "seule"))
    s.set_defaults(f=cmd_init)

    s = sp.add_parser("selftest", help=trad("injecte des défauts connus et vérifie qu'ils sont attrapés"))
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(f=cmd_selftest)

    s = sp.add_parser("fingerprint", help=trad("empreinte du moteur et de fichiers"))
    s.add_argument("files", nargs="*")
    s.set_defaults(f=cmd_fingerprint)

    s = sp.add_parser("mutation-verdict", help=trad("survivants d'un balayage contre les plafonds"))
    s.add_argument("results")
    s.add_argument("--adapter", dest="adaptateur",
                   help=trad("dans un projet à plusieurs adaptateurs, celui dont l'outil a écrit ces résultats "
                             "(le principal sinon)"))
    s.add_argument("--record", action="store_true", dest="poser",
                   help=trad("écrire le plafond mesuré des modules « à mesurer » dans les garde-fous"))
    s.set_defaults(f=cmd_mutation_verdict)

    s = sp.add_parser("mutation-run", help=trad("lance le balayage de mutation de chaque adaptateur, puis "
                                                "son verdict"))
    s.add_argument("--record", action="store_true", dest="poser",
                   help=trad("écrire le plafond mesuré des modules « à mesurer » dans les garde-fous"))
    s.set_defaults(f=cmd_mutation_run)

    s = sp.add_parser("renumber", help=trad("donne le prochain identifiant libre à une entrée qu'une autre "
                                            "branche a prise aussi"))
    s.add_argument("id")
    s.set_defaults(f=cmd_renumber)

    s = sp.add_parser("archive", help=trad("range les sujets clos du backlog à l'écart des ouverts"))
    s.set_defaults(f=cmd_archive)


    s = sp.add_parser("checks", help=trad("liste des contrôles"))
    s.set_defaults(f=cmd_checks)

    # L'aide liste les commandes par public, au lieu de la liste d'argparse.
    aides = {a.dest: a.help for a in sp._choices_actions}
    sp._choices_actions.clear()
    p.epilog = aide_groupee(aides)
    return p, aides


def _langue_de(argv: list[str]) -> str:
    """La langue de la mémoire du projet que vise la commande (`--root`, ou
    le dépôt courant) : l'aide et ce qui s'imprime avant le chargement du
    projet la suivent aussi. Le français hors d'un projet lisible."""
    racine = next((argv[i + 1] for i, x in enumerate(argv[:-1]) if x == "--root"), None) or next(
        (x.split("=", 1)[1] for x in argv if x.startswith("--root=")), None)
    try:
        return langue.du_projet(config.Projet.charger(Path(racine) if racine else None))
    except Exception:
        return messages.FRANCAIS


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # La langue que la commande pose ne lui survit pas : un appel suivant,
    # dans le même processus, part du français.
    avant = messages.choisir(_langue_de(argv))
    try:
        p, aides = analyseur()
        # Le lanceur passe `--root <racine>` devant ce que l'humain a tapé.
        if not [x for i, x in enumerate(argv) if x != "--root" and (i == 0 or argv[i - 1] != "--root")]:
            # Sans commande : l'aide courte, celle de l'humain.
            print(trad("socle {version} — mémoire, documentation et tests fiables\n", version=VERSION))
            print(aide_groupee(aides, ["pour l'humain"]))
            print(trad("\nLe guide : `python3 .socle/socle help` ; toutes les commandes : `python3 .socle/socle "
                       "--help`."))
            return 0
        args = p.parse_args(argv)
        try:
            code = args.f(args)
            # Une sortie tamponnée (128 Kio depuis Python 3.14) ne part qu'ici :
            # le tube fermé se constate dans ce bloc, pas à l'arrêt de
            # l'interpréteur, qui le dirait et rendrait 120.
            sys.stdout.flush()
            return code
        except BrokenPipeError:
            # Le lecteur s'en est allé (`| head -1`) : ce n'est pas une
            # panne. La sortie restante part dans le vide, pour que l'arrêt de
            # l'interpréteur ne retombe pas sur le même tube fermé.
            vide = os.open(os.devnull, os.O_WRONLY)
            os.dup2(vide, sys.stdout.fileno())
            return 0
    finally:
        messages.choisir(avant)
