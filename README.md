# Blockchain Supply Chain

A hybrid blockchain supply chain API for craft beer traceability built with FastAPI and Web3.

## Overview

This project provides a comprehensive solution for tracking and verifying craft beer products through the supply chain using blockchain technology.

## Features

- **FastAPI REST API** for supply chain management
- **Web3 Integration** for blockchain interactions
- **Craft Beer Traceability** with manifest and record management
- **Verification Services** for blockchain validation
- **Security** with ECDSA encryption

## Getting Started

### Requirements

- Python >= 3.12
- UV package manager

### Installation

```bash
uv sync
```

### Running the Application

```bash
python -m app.main
```

## Project Structure

- `app/` - Main application code
  - `core/` - Core utilities (database, hashing, security, settings)
  - `crud/` - Database operations
  - `models/` - SQLAlchemy models
  - `routers/` - API endpoints
  - `schemas/` - Pydantic schemas
  - `services/` - Business logic services
- `contracts/` - Solidity smart contracts
- `cli_user.py` - Command-line interface
- `verify_blockchain.py` - Blockchain verification utilities

## Dependencies

- FastAPI 0.136.1
- Web3 7.16.0
- Pydantic Settings 2.14.1
- ECDSA 0.19.2
- Rich 15.0.0

## License

MIT
