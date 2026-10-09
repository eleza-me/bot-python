"""Shared by the examples: finds the SDK and reads the token from the
environment, so it never ends up in a file.

    ELEZA_BOT_TOKEN='ezb1.…' python examples/01_echo.py
"""

import os
import sys

# Lets the examples run from a checkout, without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))


def token() -> str:
    value = os.environ.get("ELEZA_BOT_TOKEN", "")
    if not value:
        sys.exit("Set ELEZA_BOT_TOKEN to the token @BotFather gave you.")
    return value
