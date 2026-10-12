from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP


# Ensure `rag/` is importable regardless of MCP host working directory.
RAG_ROOT = Path(__file__).resolve().parents[1]
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from query import (  # noqa: E402
    COLLECTION_NAME,
    DB_DIR,
    ensure_model_exists,
    query_wiki as _query_wiki_impl,
)


mcp = FastMCP("vs-wiki-rag")


def _startup_healthcheck() -> None:
    """Fail fast with clear startup errors for missing model/collection."""
    ensure_model_exists()

    from chromadb import PersistentClient

    client = PersistentClient(path=str(DB_DIR))
    try:
        client.get_collection(name=COLLECTION_NAME)
    except Exception as exc:  # pragma: no cover - startup guard
        raise RuntimeError(
            "Chroma collection is not available at startup. "
            f"Expected collection '{COLLECTION_NAME}' under '{DB_DIR}'. "
            "Run `python embed.py` first to create/populate the index."
        ) from exc


@mcp.tool()
def query_wiki(question: str, top_k: int = 5) -> str:
    """
    Search the local Vintage Story modding wiki knowledge base.
    Use this before writing any JSON field, C# API call, class/method
    name, or VS-specific convention you are not 100% certain of —
    this wiki is the source of truth, not training data.

    Returns the top matching wiki excerpts with their source file path.
    """
    rows = _query_wiki_impl(question=question, top_k=top_k)
    if not rows:
        return "No results found."

    blocks: list[str] = []
    for i, row in enumerate(rows, start=1):
        source = row.get("source") or "(unknown)"
        category = row.get("category") or "(unknown)"
        text = (row.get("text") or "").strip()
        blocks.append(
            "\n".join(
                [
                    f"[{i}] source={source}",
                    f"category={category}",
                    "excerpt:",
                    text,
                ]
            )
        )

    return "\n\n".join(blocks)


if __name__ == "__main__":
    _startup_healthcheck()
    mcp.run(transport="stdio")
