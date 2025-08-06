# OpenAI Agents UI

This project provides a simple Flask interface for creating and managing OpenAI Agents using the OpenAI Python SDK. Agents can be configured with prompts, models, tools and guardrails. Each agent can be tested from a built‑in playground and accessed programmatically through a Chat Completions–style API.

## Features

- Create, edit and delete agents with configurable instructions, tools and guardrails.
- Test agents in a simple playground; conversation history is stored in a SQLite database.
- REST API endpoints to manage agents and send chat requests (`/api/agents`, `/api/chat/<agent_id>`).
- Configuration values such as `OPENAI_API_KEY`, model and API base URL are read from environment variables.
- Dockerfile and docker‑compose configuration with a volume for persisting the SQLite database.

## Running locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your key"
python app.py
```

Then open `http://localhost:5000` in your browser.

## Docker

```bash
docker compose up --build
```

The SQLite database is stored in the `data/` directory which is mounted as a volume.
