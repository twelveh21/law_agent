# Project structure

## Root-level files

- `.env`: local secrets and environment configuration; keep at the project root.
- `pyproject.toml` and `uv.lock`: Python project/dependency configuration; keep together at the root.
- `langgraph.json`: LangGraph CLI configuration; it refers to `app/agent/law.py` and the root `.env`.

## Folders

- `app/`: application code, split by responsibility (API, agent, services, tools, RAG, memory, and common utilities).
- `tests/`: automated tests.
- `scripts/`: command-line scripts for converting PDFs, building the knowledge base, and watching the input folder.
- `archives/`: ZIP snapshots/backups. These are kept as archives and are not loaded by the application.
- `data/`, `pdf/`, `input/`, `output/`, `db/`, and `chroma_db/`: application inputs, outputs, and persistent data; do not delete as cleanup artifacts.

## Running the scripts

Run commands from the project root so imports resolve consistently:

```powershell
python -m scripts.convert_pdf
python -m scripts.build_knowledge_base
python -m scripts.build_knowledge_base --rebuild
python -m scripts.watchdog_service
```

The `--rebuild` option deletes and recreates only the legal RAG collection, so use it only when you intend to rebuild that index.
