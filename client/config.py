"""Configuração partilhada pelo cliente CLI."""

from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
SUPPLY_MANAGER_ADDRESS = "0x9D77a7336C19eE8975Eb6267c2aF384B90C73455"
CLIENT_ENV_FILE = Path(__file__).parent / ".env"

