"""Point d'entrée de Renshū (python main.py, ou le .exe généré par build.bat)."""
import sys

from renshu.app import main

if __name__ == "__main__":
    sys.exit(main())
