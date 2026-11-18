# Double-clique sur ce fichier pour lancer Renshū (sans fenêtre noire).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from renshu.app import main  # noqa: E402

sys.exit(main())
