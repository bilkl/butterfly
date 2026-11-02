"""Exécution d'un programme Butterfly dans un sous-processus borné.

**Ce que ce module protège, et ce qu'il ne protège pas.**

Exécuter un programme écrit par une IA, c'est exécuter du code que personne n'a
relu. Les risques courants ont chacun leur parade :

| Risque                         | Parade                                          |
|--------------------------------|-------------------------------------------------|
| boucle infinie                 | délai maximal, puis ``kill``                    |
| sortie infinie                 | lecture bornée (64 Kio par flux), puis ``kill`` |
| mémoire                        | ``RLIMIT_AS`` posée par le fils (POSIX)         |
| plantage du serveur            | processus séparé : jamais d'``exec`` ici        |
| fichiers qui traînent          | dossier temporaire supprimé par un ``with``     |
| lecture de l'entrée du serveur | ``stdin=DEVNULL`` (en stdio, c'est le canal MCP)|

Ce tableau **ne protège pas** l'accès aux fichiers, au réseau ou aux autres
programmes. Pour Butterfly, c'est la **conception du langage** qui protège le
système : un programme ne peut ni lire de fichier, ni ouvrir de connexion, ni
importer un module, ni appeler du code arbitraire. Et le générateur ne laisse
passer aucun texte du programme dans le code Python : les textes sont écrits avec
``repr``, les noms de variables sont préfixés par ``v_``, et tout le reste du
Python généré est fabriqué par le compilateur. Un langage qui offrirait
``lis_fichier(...)`` demanderait un vrai bac à sable (conteneur, utilisateur
dédié, filtrage d'appels système).
"""

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RACINE = Path(__file__).resolve().parent.parent
LIMITE_SORTIE = 64 * 1024  # octets, par flux
LIMITE_MEMOIRE = 512 * 1024 * 1024  # octets d'espace d'adressage

#: Le fils pose lui-même sa limite mémoire, avant d'importer le langage (poser
#: la limite avec ``preexec_fn`` est déconseillé dès qu'il y a des threads).
CODE_DU_FILS = """\
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, ({memoire}, {memoire}))
except (ImportError, ValueError, OSError):
    pass
sys.path.insert(0, {racine!r})
from butterfly.cli import main
sys.exit(main(sys.argv[1:]))
"""

type StatutIsole = Literal[
    "ok",
    "erreur_execution",
    "delai_depasse",
    "sortie_tronquee",
    "memoire_depassee",
    "erreur_interne",
]


@dataclass(frozen=True)
class ResultatIsole:
    statut: StatutIsole
    sortie: str
    erreur: str  # ce que le fils a écrit sur stderr
    duree: float


def environnement() -> dict[str, str]:
    """Un environnement réduit : le fils n'hérite pas des variables du serveur."""
    return {nom: os.environ[nom] for nom in ("SYSTEMROOT",) if nom in os.environ}


@contextmanager
def processus(args: list[str], cwd: Path) -> Iterator[subprocess.Popen[bytes]]:
    """Lance un processus, et le tue et ferme ses tubes quoi qu'il arrive."""
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        env=environnement(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        for flux in (proc.stdout, proc.stderr):
            if flux is not None:
                flux.close()


def _lire_borne(
    flux: int, limite: int, tampon: bytearray, depasse: threading.Event
) -> None:
    """Lit un flux par morceaux ; s'arrête dès que la limite est dépassée."""
    while True:
        try:
            morceau = os.read(flux, 4096)
        except OSError:
            return
        if not morceau:
            return
        tampon.extend(morceau)
        if len(tampon) > limite:
            depasse.set()
            return


def executer_isole(
    source: str,
    delai: float = 2.0,
    limite_sortie: int = LIMITE_SORTIE,
    limite_memoire: int = LIMITE_MEMOIRE,
) -> ResultatIsole:
    """Exécute ``source`` (déjà vérifié) dans un processus séparé et borné."""
    code = CODE_DU_FILS.format(memoire=limite_memoire, racine=str(RACINE))
    debut = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="butterfly-") as dossier:
        travail = Path(dossier)
        # Le fils tourne DANS le dossier temporaire, avec un chemin relatif :
        # les messages d'erreur ne révèlent pas le chemin du dossier.
        (travail / "programme.fly").write_text(source, encoding="utf-8")
        args = [sys.executable, "-I", "-X", "utf8", "-c", code, "run", "programme.fly"]
        with processus(args, travail) as proc:
            assert proc.stdout is not None and proc.stderr is not None
            sortie, erreur = bytearray(), bytearray()
            depasse = threading.Event()
            lecteurs = [
                threading.Thread(
                    target=_lire_borne,
                    args=(flux.fileno(), limite_sortie, tampon, depasse),
                    daemon=True,
                )
                for flux, tampon in ((proc.stdout, sortie), (proc.stderr, erreur))
            ]
            for lecteur in lecteurs:
                lecteur.start()
            statut = _attendre(proc, depasse, debut + delai)
            for lecteur in lecteurs:
                lecteur.join(timeout=1.0)
            code_retour = proc.returncode
    texte_sortie = bytes(sortie[:limite_sortie]).decode("utf-8", errors="replace")
    texte_erreur = bytes(erreur[:limite_sortie]).decode("utf-8", errors="replace")
    if statut is None:
        statut = _classer(code_retour, texte_erreur)
    return ResultatIsole(statut, texte_sortie, texte_erreur, time.monotonic() - debut)


def _attendre(
    proc: subprocess.Popen[bytes], depasse: threading.Event, fin: float
) -> StatutIsole | None:
    """Attend la fin du fils. Renvoie un statut si on a dû le tuer, sinon None."""
    while proc.poll() is None:
        if depasse.is_set():
            proc.kill()
            return "sortie_tronquee"
        if time.monotonic() >= fin:
            proc.kill()
            return "delai_depasse"
        time.sleep(0.005)
    if depasse.is_set():
        return "sortie_tronquee"
    return None


def _classer(code_retour: int | None, erreur: str) -> StatutIsole:
    if code_retour == 0:
        return "ok"
    if "MemoryError" in erreur:
        return "memoire_depassee"
    if code_retour == 1 and "Erreur d'exécution" in erreur:
        return "erreur_execution"
    return "erreur_interne"


ERREUR_EXECUTION = re.compile(r"Erreur d'exécution \(ligne (\d+)\) : (.+)")


def lire_erreur_execution(erreur: str) -> tuple[int, str] | None:
    """(ligne, message) d'une erreur d'exécution écrite sur stderr, ou None."""
    trouve = ERREUR_EXECUTION.search(erreur)
    return (int(trouve.group(1)), trouve.group(2)) if trouve else None
