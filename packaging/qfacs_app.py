"""Entry point of the packaged qFACS program (built with PyInstaller, see .github/workflows/build-app.yml).

Double-click (no arguments): opens qFACS as a page in the browser.
With arguments it is the normal command line, e.g. `qFACS.exe analyze setup.xlsx folder`.
"""
import sys

from qfacs.__main__ import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["app"]))
