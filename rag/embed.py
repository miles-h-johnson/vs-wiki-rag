from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import re

EXPECTED_FILE_COUNT = 120
COLLECTION_NAME = "vs_wiki"
DOCUMENT_PREFIX = "search_document: "

TOKEN_TARGET = 500
TOKEN_OVERLAP_RATIO = 0.10
TOKEN_OVERLAP = int(TOKEN_TARGET * TOKEN_OVERLAP_RATIO)
TOKEN_STEP = TOKEN_TARGET - TOKEN_OVERLAP

HEADER_RE = re.compile(r"^(#{1,2})\s+")
TITLE_RE = re.compile(r"^#\s+(?:Modding:)?(.+)$", re.MULTILINE)
TOKEN_RE = re.compile(r"\S+")

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = (ROOT / "../vs_modding_wiki/cleaned").resolve()
DB_DIR = ROOT / "db"
MODEL_PATH = ROOT / "models/nomic-embed-text-v1.5.Q8_0.gguf"

# About a third of chunks exceed 512 tokens and are truncated; embedding them whole
# (--n-ctx 8192) scored no better on eval/, so the cheaper default stays.
N_CTX = 512
# Vectors are unnormalised but their norms vary little (p10-p90: 17.9-20.6), so cosine
# ranked the same as L2 on eval/.
DEFAULT_SPACE = "l2"


@dataclass
class Chunk:
    source: str
    category: str
    chunk_index: int
    text: str
    title: str


def approx_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def split_oversize(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + TOKEN_TARGET, len(words))
        chunks.append(" ".join(words[start:end]))

        if end >= len(words):
            break

        start += TOKEN_STEP

    return chunks


def chunk_markdown_header_aware(text: str) -> list[str]:
    lines = text.splitlines()

    sections: list[tuple[str, str]] = []
    current_header = "(preamble)"
    buffer: list[str] = []

    for line in lines:
        if HEADER_RE.match(line):
            if buffer:
                body = "\n".join(buffer).strip()
                if body:
                    sections.append((current_header, body))
                buffer = []

            current_header = line.strip()
            buffer.append(line)
        else:
            buffer.append(line)

    if buffer:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current_header, body))

    chunks: list[str] = []
    for _header, body in sections:
        token_count = approx_tokens(body)
        if token_count <= TOKEN_TARGET:
            chunks.append(body)
        else:
            chunks.extend(split_oversize(body))

    return chunks


def collect_markdown_files(source_dir: Path) -> list[Path]:
    return sorted(source_dir.rglob("*.md"))


def chunks_for_file(source_dir: Path, file_path: Path) -> list[Chunk]:
    relative_path = file_path.relative_to(source_dir).as_posix()
    category = relative_path.split("/", 1)[0] if "/" in relative_path else "root"

    raw_text = file_path.read_text(encoding="utf-8")
    text_chunks = chunk_markdown_header_aware(raw_text)
    title_match = TITLE_RE.search(raw_text)
    title = title_match.group(1).strip() if title_match else file_path.stem.replace("_", " ")

    return [
        Chunk(
            source=relative_path,
            category=category,
            chunk_index=i,
            text=chunk_text,
            title=title,
        )
        for i, chunk_text in enumerate(text_chunks)
    ]


def iter_all_chunks(source_dir: Path, files: Iterable[Path]) -> Iterable[Chunk]:
    for file_path in files:
        yield from chunks_for_file(source_dir, file_path)


def run_dry_run(source_dir: Path, sample_files: list[str] | None) -> None:
    md_files = collect_markdown_files(source_dir)
    print(f"Found {len(md_files)} markdown files under {source_dir}")
    if len(md_files) != EXPECTED_FILE_COUNT:
        print(
            f"WARNING: expected {EXPECTED_FILE_COUNT} files in cleaned/, found {len(md_files)}"
        )

    if sample_files:
        targets = [source_dir / rel for rel in sample_files]
    else:
        targets = [
            source_dir / "Code/Advanced_Code_Tutorials.md",
            source_dir / "Code/Basic_Code_Tutorials.md",
            source_dir / "AssetTypes/Block_Json_Properties.md",
        ]

    for target in targets:
        rel = target.relative_to(source_dir).as_posix() if target.exists() else str(target)
        print(f"\n=== {rel}")
        print(f"exists={target.exists()}")
        if not target.exists():
            continue

        chunks = chunks_for_file(source_dir, target)
        token_sizes = [approx_tokens(c.text) for c in chunks]
        fallback_chunks = sum(1 for size in token_sizes if size >= TOKEN_TARGET)

        print(f"chunk_count={len(chunks)} fallback_chunks~={fallback_chunks}")
        if token_sizes:
            token_sizes_sorted = sorted(token_sizes)
            p50 = token_sizes_sorted[len(token_sizes_sorted) // 2]
            print(
                f"token_stats min={min(token_sizes)} p50={p50} max={max(token_sizes)}"
            )
            print(f"first_sizes={token_sizes[:15]}")
            print(f"last_sizes={token_sizes[-8:]}")


def index_all(source_dir: Path, db_dir: Path, space: str, n_ctx: int, title_prefix: bool) -> None:
    from chromadb import PersistentClient
    from llama_cpp import Llama

    md_files = collect_markdown_files(source_dir)
    print(f"Found {len(md_files)} markdown files under {source_dir}")
    if len(md_files) != EXPECTED_FILE_COUNT:
        print(
            f"WARNING: expected {EXPECTED_FILE_COUNT} files in cleaned/, found {len(md_files)}"
        )

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found at expected path: {MODEL_PATH}\n"
            "Place nomic-embed-text-v1.5.Q8_0.gguf in rag/models/ before running index mode."
        )

    db_dir.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(path=str(db_dir))
    # Rebuilt from scratch: the distance space is fixed when a collection is created.
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(
        name=COLLECTION_NAME, configuration={"hnsw": {"space": space}}
    )

    llm = Llama(
        model_path=str(MODEL_PATH),
        embedding=True,
        n_gpu_layers=-1,
        n_ctx=n_ctx,
        n_batch=n_ctx,
        n_ubatch=n_ctx,
        verbose=False,
    )

    for file_path in md_files:
        file_chunks = chunks_for_file(source_dir, file_path)
        rel_source = file_path.relative_to(source_dir).as_posix()

        if not file_chunks:
            continue

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []
        embeddings: list[list[float]] = []

        for chunk in file_chunks:
            ids.append(str(uuid.uuid4()))
            # Only a page's first chunk carries its title; without it, later chunks can't
            # match questions that use the page's topic but none of the section's words.
            context = f"{chunk.title}\n\n" if title_prefix else ""
            prefixed_text = DOCUMENT_PREFIX + context + chunk.text
            documents.append(chunk.text)
            metadatas.append(
                {
                    "source": chunk.source,
                    "category": chunk.category,
                    "chunk_index": chunk.chunk_index,
                    "title": chunk.title,
                }
            )
            embeddings.append(llm.embed(prefixed_text))

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        print(f"Indexed {len(file_chunks)} chunks from {rel_source}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vintage Story wiki embedding pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run chunking/file-count validation only (no model load, no DB writes).",
    )
    parser.add_argument(
        "--sample",
        action="append",
        default=None,
        help="Relative file path in cleaned/ to inspect in dry-run mode. Can be repeated.",
    )
    parser.add_argument("--db", type=Path, default=DB_DIR, help="Chroma persistence folder (rebuilt).")
    parser.add_argument("--space", choices=("cosine", "l2"), default=DEFAULT_SPACE)
    parser.add_argument("--n-ctx", type=int, default=N_CTX, help="Embedding context; longer chunks are truncated.")
    parser.add_argument(
        "--title-prefix",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Prepend the page title to each chunk before embedding.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        run_dry_run(SOURCE_DIR, args.sample)
        return

    index_all(SOURCE_DIR, args.db, args.space, args.n_ctx, args.title_prefix)


if __name__ == "__main__":
    main()
