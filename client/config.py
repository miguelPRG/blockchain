"""Configuração partilhada pelo cliente CLI."""

import os
from pathlib import Path

CLIENT_ENV_FILE = Path(__file__).parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(CLIENT_ENV_FILE)
except Exception:
    pass

BASE_URL = "http://127.0.0.1:8000"


def _required_env_address(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    raise RuntimeError(f"Missing required address in {CLIENT_ENV_FILE}: {' or '.join(names)}")


ALICE_ADDRESS = _required_env_address("ALICE_ADDRESS", "ALICE_PUBLIC_ADDRESS")
BOB_ADDRESS = _required_env_address("BOB_ADDRESS", "BOB_PUBLIC_ADDRESS")
CHARLIE_ADDRESS = _required_env_address("CHARLIE_ADDRESS", "CHARLIE_PUBLIC_ADDRESS")
SUPPLY_MANAGER_ADDRESS = _required_env_address(
    "SUPPLY_MANAGER_ADDRESS",
    "MANAGER_ADDRESS",
    "MANAGER_PUBLIC_ADDRESS",
)
