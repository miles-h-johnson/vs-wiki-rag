# vs-wiki-rag

Local retrieval over the Vintage Story modding wiki, served to coding agents as an MCP tool.

Coding assistants guess at game-modding APIs they have barely seen in training. This project downloads the official modding wiki, cleans it, embeds it on the local GPU and exposes one tool, `query_wiki`, so an agent can look up the real API before it writes code. Everything runs offline after the download; no hosted model or API key is involved.

## How it works

1. **Download** (`rag/download_vs_modding_wiki.py`): fetches the 133 pages in the wiki's Modding category and converts them to Markdown.
2. **Clean** (`rag/clean_wiki.py`): drops the index and navigation-only portal pages, strips images and the navigation boxes appended to every page, and trims whitespace. 120 pages remain.
3. **Chunk and embed** (`rag/embed.py`): splits each page at `#` and `##` headings, falls back to 500-word windows with 10% overlap for long sections, prepends the page title, and embeds with [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF) (Q8 GGUF via llama.cpp) using the model's `search_document:` / `search_query:` prefixes. The result is 700 chunks in a local ChromaDB collection; a full rebuild takes about 15 seconds on an RTX 4090.
4. **Query** (`rag/query.py`, `rag/mcp-server/server.py`): embeds the question, returns the top matches with their source page. The MCP server checks at startup that the model and index exist, so a misconfigured agent fails loudly rather than silently getting no results.

## Evaluation

`eval/questions.jsonl` holds 40 questions phrased the way a modder would ask them ("How do I send a custom packet from the server to the client?"), each labelled with the page or pages that answer it. `eval/run_eval.py` counts a hit when a chunk from an answering page appears in the top *k* results.

| Setup | hit@1 | hit@3 | hit@5 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| Original index (chunks joined with a literal `\n`, unrecorded cleaning step) | 57.5% | 82.5% | 87.5% | 0.702 |
| Baseline: newline bug fixed, `clean_wiki.py` | 57.5% | 87.5% | 87.5% | 0.716 |
| Baseline + cosine distance | 57.5% | 82.5% | 87.5% | 0.702 |
| Baseline + 8,192-token context | 55.0% | 87.5% | 87.5% | 0.702 |
| **Baseline + page title on every chunk (default)** | **57.5%** | **90.0%** | **90.0%** | **0.728** |

What the numbers say:

- **Prepending the page title is the one change that helped.** Only a page's first chunk carried its title, so later chunks could not match a question about the page's topic.
- **Cosine distance made no difference.** llama.cpp returns unnormalised vectors, which looked like a problem for L2 distance, but their norms vary little (p10–p90: 17.9–20.6), so both metrics rank the same.
- **A longer context made no difference.** A third of chunks exceed llama-cpp-python's default 512-token context and are truncated. Embedding them whole did not score better, so the default stays at 512.
- **The set is small.** One question is 2.5 points, so differences under about 5 points are noise. The table shows direction, not significance.

Two labels were widened after the first run, because the retrieved pages also answered the question (marked with `note` in the file); all rows above are scored against the final labels. The questions were written from page titles before any retrieval was run.

The four remaining misses describe a problem in different words from the answer page's title and headings: "reuse the properties of another block" should find *InheritFrom*, and "renamed block codes, missing blocks" should find *The Remapper*. Hybrid keyword and vector search, or rewriting the query before retrieval, are the obvious next steps.

## Setup

Requires Python 3.12. A CUDA build of llama-cpp-python is optional but makes indexing fast.

```powershell
cd rag
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# download nomic-embed-text-v1.5.Q8_0.gguf from Hugging Face into rag/models/
python download_vs_modding_wiki.py
python clean_wiki.py
python embed.py
python query.py "How do I register a block behavior?"
```

Run the evaluation from the repository root with `python eval/run_eval.py`. `embed.py --space cosine --n-ctx 8192 --no-title-prefix --db <folder>` reproduces the other rows of the table.

## Use from Claude Code

```powershell
claude mcp add vs-wiki-rag -- <path-to>\rag\venv\Scripts\python.exe <path-to>\rag\mcp-server\server.py
```

The tool description tells the agent to check the wiki before writing any Vintage Story JSON field, class or method name it is not certain of.

## Data

Wiki content is downloaded from [wiki.vintagestory.at](https://wiki.vintagestory.at) at run time and is not included in this repository.
