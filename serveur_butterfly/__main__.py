"""Point d'entrée : ``python -m serveur_butterfly`` (ou ``butterfly-mcp``).

Le serveur parle MCP en **stdio** : l'hôte (Claude Code, Claude Desktop, un IDE)
le lance comme sous-processus et dialogue sur son entrée et sa sortie standard.
Pour cette raison, **rien ne doit être écrit sur stdout** en dehors du protocole :
pour tracer quelque chose, écrire sur ``sys.stderr``.
"""

from serveur_butterfly.serveur import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
