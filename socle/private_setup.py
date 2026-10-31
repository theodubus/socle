"""Le mode compagnon mis en place d'un geste :
`socle private install`, réservé à l'humain. Séparé de `prive`, qui lit et
contrôle la zone privée."""

from __future__ import annotations

from pathlib import Path

from socle import config, utils as outils
from socle.messages import trad
from socle.private import adresse_ssh, commit_compagnon, depot_compagnon, dossier, ecrire_verrou, fichier_verrou, mode


def installer_compagnon(projet: config.Projet, adresse: str) -> tuple[int, list[str]]:
    """Le mode compagnon mis en place d'un geste : le dépôt privé
    cloné, son premier commit poussé s'il est vide, le verrou écrit, une clé
    de déploiement créée ; puis ce qui reste à faire sur GitHub, avec les
    liens. Réservé à l'humain : il pousse vers le dépôt privé et crée une clé."""
    import shutil
    import subprocess

    from socle import links as liens

    racine = projet.racine
    if mode(projet) != "compagnon":
        return 1, [trad("refus : la politique ne choisit pas le mode compagnon — relancer l'installation avec "
                        "`--private compagnon`, qui l'écrit")]
    rel = dossier(racine)
    zone = racine / rel
    res = []
    if depot_compagnon(racine) is None:
        if zone.exists() and any(zone.iterdir()):
            return 1, [trad("refus : {rel}/ existe et n'est pas un clone : le déplacer, puis relancer", rel=rel)]
        r = subprocess.run(["git", "clone", "-q", adresse, str(zone)], cwd=racine, capture_output=True, text=True)
        if r.returncode != 0:
            return 1, [trad("refus : clone impossible ({erreur})",
                            erreur=r.stderr.strip()[-300:] or trad("git clone a échoué"))]
        res.append(trad("dépôt privé cloné dans {rel}/", rel=rel))
    else:
        res.append(trad("dépôt privé déjà cloné dans {rel}/", rel=rel))
    if outils.ajouter_lignes(racine / ".gitignore", [f"{rel}/"], trad("# Le clone du dépôt privé (mémoire "
                                                                      "privée)")):
        res.append(trad("{rel}/ ignoré par le dépôt public (.gitignore)", rel=rel))
    if not outils.a_des_commits(zone):
        (zone / "README.md").write_text(
            trad("# Mémoire privée de {projet}\n\nLe socle y range la mémoire privée du projet, au même format "
                 "que la mémoire publique. Ce dépôt reste privé.\n", projet=racine.name), encoding="utf-8")
        for args in (["add", "README.md"], ["commit", "-q", "-m", trad("Mémoire privée : premier commit")]):
            r = subprocess.run(["git", *args], cwd=zone, capture_output=True, text=True)
            if r.returncode != 0:
                return 1, res + [trad("refus : premier commit du dépôt privé impossible ({erreur})",
                                      erreur=r.stderr.strip()[-300:])]
        res.append(trad("premier commit du dépôt privé"))
    sha = commit_compagnon(racine)
    # La CI clone le dépôt privé au commit du verrou : il doit y être poussé.
    r = subprocess.run(["git", "push", "-q", "-u", "origin", "HEAD"], cwd=zone, capture_output=True, text=True)
    if r.returncode != 0:
        res.append(trad("!! dépôt privé non poussé ({erreur}) : le pousser, sans quoi la CI ne trouvera pas le "
                        "commit du verrou", erreur=r.stderr.strip()[-200:]))
    else:
        res.append(trad("dépôt privé poussé"))
    ecrire_verrou(racine, sha)
    res.append(trad("verrou : {sha} ({verrou})", sha=sha[:10], verrou=fichier_verrou(racine)))

    cle = config.chemin_trace(racine).parent / "prive-deploiement"
    if not cle.is_file():
        cle.parent.mkdir(parents=True, exist_ok=True)
        if shutil.which("ssh-keygen"):
            r = subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", f"socle CI {racine.name}",
                                "-f", str(cle)], capture_output=True, text=True)
            if r.returncode != 0:
                res.append(trad("!! clé de déploiement non créée ({erreur})", erreur=r.stderr.strip()[-200:]))
        else:
            res.append(trad('!! ssh-keygen absent : créer la clé à la main, `ssh-keygen -t ed25519 -N "" -f '
                            "{cle}`", cle=cle))
    if cle.is_file():
        res.append(trad("clé de déploiement : {cle} (hors du dépôt, jamais commitée)", cle=cle))

    res += [""] + gestes_github(adresse, liens.url_depot(projet), cle)
    res += ["", trad("Ensuite :"),
            trad("  - effacer la clé privée une fois le secret posé : rm {cle}", cle=cle),
            trad('  - commiter puis pousser : git add {verrou} .gitignore && git commit -m "Mémoire '
                 'privée : le dépôt compagnon" && git push', verrou=fichier_verrou(racine))]
    return 0, res


def gestes_github(adresse: str, web_public: str | None, cle: Path) -> list[str]:
    """Les deux gestes qui restent à l'humain sur GitHub, avec les liens des
    pages où les faire quand les dépôts y sont, et les commandes `gh`."""
    from socle import links as liens

    ssh = adresse_ssh(adresse)
    web_prive = liens.depuis_distant(adresse)
    github = (web_prive or "").startswith("https://github.com/")
    res = [trad("Sur GitHub, deux gestes :"),
           trad("  1. la clé publique en clé de déploiement du dépôt privé, en lecture seule")
           + (f" : {web_prive}/settings/keys/new" if github else ""),
           trad("     (le contenu de {cle}.pub)", cle=cle),
           trad("  2. deux secrets du dépôt public") + (f" : {web_public}/settings/secrets/actions/new"
                                                        if web_public and github else ""),
           f"     SOCLE_PRIVE_DEPOT = {ssh}",
           trad("     SOCLE_PRIVE_CLE   = le contenu de {cle}", cle=cle)]
    if github:
        depot = web_prive.removeprefix("https://github.com/")
        res += [trad("  Ou, avec gh :"),
                f"     gh repo deploy-key add {cle}.pub --repo {depot} --title \"socle CI\"",
                f"     gh secret set SOCLE_PRIVE_DEPOT --body \"{ssh}\"",
                f"     gh secret set SOCLE_PRIVE_CLE < {cle}"]
    return res
