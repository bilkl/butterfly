"""Butterfly : un langage réactif, transpilé en Python.

Changer une valeur peut mettre à jour tout un programme : c'est l'effet
papillon. La chaîne de compilation, écrite à la main, est :

    texte → lexer → tokens → parser → arbre → analyse → arbre vérifié → Python

La façade publique est dans ``butterfly.compilateur``.
"""

__version__ = "0.1.0"
