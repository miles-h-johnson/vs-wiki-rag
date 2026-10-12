from __future__ import annotations

import argparse
from pathlib import Path


COLLECTION_NAME = "vs_wiki"
QUERY_PREFIX = "search_query: "

ROOT = Path(__file__).resolve().parent
DB_DIR = ROOT / "db"
MODEL_PATH = ROOT / "models/nomic-embed-text-v1.5.Q8_0.gguf"


def ensure_model_exists() -> Path:
    """Return model path or raise a clear error if missing."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Model file not found at expected path: "
            f"{MODEL_PATH}\n"
            "Place nomic-embed-text-v1.5.Q8_0.gguf in rag/models/ before querying."
        )
    return MODEL_PATH


def _truncate_for_display(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


_llm: "Llama | None" = None  # lazy singleton


def _get_llm() -> "Llama":
    global _llm
    if _llm is None:
        ensure_model_exists()
        from llama_cpp import Llama

        _llm = Llama(
            model_path=str(MODEL_PATH),
            embedding=True,
            n_gpu_layers=-1,
            verbose=False,
        )
    return _llm


def query_wiki(question: str, top_k: int = 5) -> list[dict]:
    """Returns list of {text, source, category, chunk_index, distance}."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if top_k <= 0:
        raise ValueError("top_k must be >= 1")

    from chromadb import PersistentClient

    client = PersistentClient(path=str(DB_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)

    llm = _get_llm()
    prefixed_query = QUERY_PREFIX + question.strip()
    query_embedding = llm.embed(prefixed_query)

    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    rows: list[dict] = []
    for text, meta, dist in zip(docs, metas, dists):
        meta = meta or {}
        rows.append(
            {
                "text": text,
                "source": meta.get("source"),
                "category": meta.get("category"),
                "chunk_index": meta.get("chunk_index"),
                "distance": dist,
            }
        )

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Vintage Story wiki Chroma index")
    parser.add_argument("question", nargs="?", help='Question text, e.g. "How do block behaviors work?"')
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return (default: 5)")
    parser.add_argument(
        "--check-model-path",
        action="store_true",
        help="Only validate that rag/models/nomic-embed-text-v1.5.Q8_0.gguf exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check_model_path:
        path = ensure_model_exists()
        print(f"Model OK: {path}")
        return

    if not args.question:
        raise SystemExit('Usage: python query.py "your question here"')

    results = query_wiki(args.question, top_k=args.top_k)
    if not results:
        print("No results found.")
        return

    for i, row in enumerate(results, start=1):
        print(f"\n[{i}] source={row.get('source')} category={row.get('category')} chunk_index={row.get('chunk_index')}")
        print(f"distance={row.get('distance')}")
        print(_truncate_for_display(row.get("text", ""), limit=300))


if __name__ == "__main__":
    main()