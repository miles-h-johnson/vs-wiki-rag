from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
RAG_DIR = EVAL_DIR.parent / "rag"
sys.path.insert(0, str(RAG_DIR))

from query import COLLECTION_NAME, DB_DIR, QUERY_PREFIX, _get_llm  # noqa: E402

CUTOFFS = (1, 3, 5)


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def first_relevant_rank(sources: list[str], expected: set[str]) -> int | None:
    for rank, source in enumerate(sources, start=1):
        if source in expected:
            return rank
    return None


def evaluate(db_dir: Path, collection_name: str, questions: list[dict], top_k: int) -> dict:
    from chromadb import PersistentClient

    collection = PersistentClient(path=str(db_dir)).get_collection(name=collection_name)
    llm = _get_llm()

    rows = []
    for item in questions:
        embedding = llm.embed(QUERY_PREFIX + item["q"])
        result = collection.query(query_embeddings=[embedding], n_results=top_k, include=["metadatas"])
        sources = [(meta or {}).get("source") for meta in result["metadatas"][0]]
        rows.append({
            "q": item["q"],
            "expected": item["expected"],
            "rank": first_relevant_rank(sources, set(item["expected"])),
            "top_sources": sources[:5],
        })

    n = len(rows)
    summary = {f"hit@{k}": sum(1 for r in rows if r["rank"] and r["rank"] <= k) / n for k in CUTOFFS}
    summary[f"mrr@{top_k}"] = sum(1 / r["rank"] for r in rows if r["rank"]) / n
    summary["questions"] = n
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval eval: does the right wiki page come back?")
    parser.add_argument("--db", type=Path, default=DB_DIR, help="Chroma persistence folder")
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument("--questions", type=Path, default=EVAL_DIR / "questions.jsonl")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--label", default="current", help="Name for the results file in eval/results/")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate(args.db, args.collection, load_questions(args.questions), args.top_k)

    out_dir = EVAL_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{args.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2))
    for row in report["rows"]:
        if not row["rank"] or row["rank"] > 3:
            print(f"rank={row['rank']}  {row['q']}\n    expected={row['expected']}\n    got={row['top_sources'][:3]}")


if __name__ == "__main__":
    main()
