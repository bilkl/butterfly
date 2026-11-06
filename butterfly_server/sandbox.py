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

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_LIMIT = 64 * 1024  # octets, par flux
MEMORY_LIMIT = 512 * 1024 * 1024  # octets d'espace d'adressage

#: Le fils pose lui-même sa limite mémoire, avant d'importer le langage (poser
#: la limite avec ``preexec_fn`` est déconseillé dès qu'il y a des threads).
CHILD_CODE = """\
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, ({memory}, {memory}))
except (ImportError, ValueError, OSError):
    pass
sys.path.insert(0, {root!r})
from butterfly.cli import main
sys.exit(main(sys.argv[1:]))
"""

type IsolatedStatus = Literal[
    "ok",
    "execution_error",
    "timeout",
    "output_truncated",
    "memory_exceeded",
    "internal_error",
]


@dataclass(frozen=True)
class IsolatedResult:
    status: IsolatedStatus
    output: str
    error: str  # ce que le fils a écrit sur stderr
    duration: float


def environment() -> dict[str, str]:
    """Un environnement réduit : le fils n'hérite pas des variables du serveur."""
    return {name: os.environ[name] for name in ("SYSTEMROOT",) if name in os.environ}


@contextmanager
def process(args: list[str], cwd: Path) -> Iterator[subprocess.Popen[bytes]]:
    """Lance un processus, et le tue et ferme ses tubes quoi qu'il arrive."""
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        env=environment(),
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
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


def _read_bound(
    stream: int, limit: int, buffer: bytearray, exceeded: threading.Event
) -> None:
    """Lit un flux par morceaux ; s'arrête dès que la limite est dépassée."""
    while True:
        try:
            piece = os.read(stream, 4096)
        except OSError:
            return
        if not piece:
            return
        buffer.extend(piece)
        if len(buffer) > limit:
            exceeded.set()
            return


def execute_isolated(
    source: str,
    time_limit: float = 2.0,
    output_limit: int = OUTPUT_LIMIT,
    memory_limit: int = MEMORY_LIMIT,
) -> IsolatedResult:
    """Exécute ``source`` (déjà vérifié) dans un processus séparé et borné."""
    code = CHILD_CODE.format(memory=memory_limit, root=str(ROOT))
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="butterfly-") as folder:
        work = Path(folder)
        # Le fils tourne DANS le dossier temporaire, avec un chemin relatif :
        # les messages d'erreur ne révèlent pas le chemin du dossier.
        (work / "program.fly").write_text(source, encoding="utf-8")
        args = [sys.executable, "-I", "-X", "utf8", "-c", code, "run", "program.fly"]
        with process(args, work) as proc:
            assert proc.stdout is not None and proc.stderr is not None
            output, error = bytearray(), bytearray()
            exceeded = threading.Event()
            readers = [
                threading.Thread(
                    target=_read_bound,
                    args=(stream.fileno(), output_limit, buffer, exceeded),
                    daemon=True,
                )
                for stream, buffer in ((proc.stdout, output), (proc.stderr, error))
            ]
            for reader in readers:
                reader.start()
            status = _wait(proc, exceeded, start + time_limit)
            for reader in readers:
                reader.join(timeout=1.0)
            return_code = proc.returncode
    output_text = bytes(output[:output_limit]).decode("utf-8", errors="replace")
    error_message = bytes(error[:output_limit]).decode("utf-8", errors="replace")
    if status is None:
        status = _classify(return_code, error_message)
    return IsolatedResult(status, output_text, error_message, time.monotonic() - start)


def _wait(
    proc: subprocess.Popen[bytes], exceeded: threading.Event, end: float
) -> IsolatedStatus | None:
    """Attend la fin du fils. Renvoie un statut si on a dû le tuer, sinon None."""
    while proc.poll() is None:
        if exceeded.is_set():
            proc.kill()
            return "output_truncated"
        if time.monotonic() >= end:
            proc.kill()
            return "timeout"
        time.sleep(0.005)
    if exceeded.is_set():
        return "output_truncated"
    return None


def _classify(return_code: int | None, error: str) -> IsolatedStatus:
    if return_code == 0:
        return "ok"
    if "MemoryError" in error:
        return "memory_exceeded"
    if return_code == 1 and "Runtime error" in error:
        return "execution_error"
    return "internal_error"


EXECUTION_ERROR = re.compile(r"Runtime error \(line (\d+)\): (.+)")


def read_execution_error(error: str) -> tuple[int, str] | None:
    """(ligne, message) d'une erreur d'exécution écrite sur stderr, ou None."""
    found = EXECUTION_ERROR.search(error)
    return (int(found.group(1)), found.group(2)) if found else None
