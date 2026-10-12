#!/usr/bin/env python3
"""
Vintage Story Modding Wiki Downloader
======================================
Downloads all 133 modding pages from https://wiki.vintagestory.at
and saves them as clean Markdown files, organised into subfolders.

Requirements:
    pip install requests html2text beautifulsoup4

Usage:
    python download_vs_modding_wiki.py

Output:
    ./vs_modding_wiki/
        index.md          <- table of contents with links to every page
        Basics/
        Content/
        Code/
        AssetTypes/
        ModelCreator/
        Troubleshooting/
        Engine/
        Other/
"""

import os
import re
import time
import requests
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    import html2text
except ImportError:
    print("Missing dependencies. Run:  pip install requests html2text beautifulsoup4")
    raise

BASE_URL = "https://wiki.vintagestory.at"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "vs_modding_wiki"
DELAY = 0.5   # seconds between requests – be polite to the server

# ── Complete page list (133 pages from Category:Modding) ─────────────────────
PAGES = [
    # A
    ("Modding:Adding_Block_Behavior",           "Code"),
    ("Modding:Advanced_Code_Tutorials",         "Code"),
    ("Modding:Advanced_Content_Tutorials",      "Content"),
    ("Modding:Animation",                       "Content"),
    ("Modding:Asset_Patching_in_Code",          "Code"),
    ("Modding:Asset_System",                    "Basics"),
    ("Modding:Asset_Type_-_BlockTypes",         "AssetTypes"),
    ("Modding:Asset_Type_-_Entities",           "AssetTypes"),
    ("Modding:Asset_Type_-_ItemTypes",          "AssetTypes"),
    ("Modding:Asset_Type_-_Language",           "AssetTypes"),
    ("Modding:Asset_Type_-_Patches",            "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes",            "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Alloy)",    "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Barrel)",   "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Clayforming)", "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Cooking)",  "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Grid)",     "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Knapping)", "AssetTypes"),
    ("Modding:Asset_Type_-_Recipes_(Smithing)", "AssetTypes"),
    ("Modding:Asset_Type_-_Shapes",             "AssetTypes"),
    ("Modding:Asset_Type_-_Sounds",             "AssetTypes"),
    ("Modding:Asset_Type_-_Textures",           "AssetTypes"),
    ("Modding:Asset_Type_-_WorldProperties",    "AssetTypes"),
    ("Modding:Asset_Types_Portal",              "AssetTypes"),
    # B
    ("Modding:Basic_Code_Tutorials",            "Code"),
    ("Modding:Basic_Content_Tutorials",         "Content"),
    ("Modding:Basic_Entity",                    "Content"),
    ("Modding:Basic_Inventory_Handling",        "Code"),
    ("Modding:Block_and_Item_Interactions",     "Code"),
    ("Modding:Block_Classes",                   "Code"),
    ("Modding:Block_Entity",                    "Code"),
    ("Modding:Block_Entity_Behaviors",          "Code"),
    ("Modding:Block_Entity_Classes",            "Code"),
    ("Modding:Block_Json_Properties",           "AssetTypes"),
    # C
    ("Modding:Chunk_Moddata",                   "Code"),
    ("Client_startup_parameters",               "Other"),
    ("Modding:Code_Basics_Portal",              "Code"),
    ("Modding:Code_Guides_Portal",              "Code"),
    ("Modding:Code_Mods",                       "Code"),
    ("Modding:Code_Mods_Portal",                "Code"),
    ("Modding:Code_Tutorial_Essentials",        "Code"),
    ("Modding:Code_Tutorial_Simple_Block",      "Code"),
    ("Modding:Code_Tutorial_Simple_Item",       "Code"),
    ("Modding:Code_Tutorials_Portal",           "Code"),
    ("Modding:Collectible_Behaviors",           "Code"),
    ("Modding:Commands",                        "Code"),
    ("Modding:Community_Resources",             "Other"),
    ("Modding:CompatibilityLib",                "Code"),
    ("Modding:Content_Basics_Portal",           "Content"),
    ("Modding:Content_Guides_Portal",           "Content"),
    ("Modding:Content_Mods",                    "Content"),
    ("Modding:Content_Mods_Portal",             "Content"),
    ("Modding:Content_Tutorial_Basics",         "Content"),
    ("Modding:Content_Tutorial_Block_Variants", "Content"),
    ("Modding:Content_Tutorial_Complex_Grid_Recipes", "Content"),
    ("Modding:Content_Tutorial_Entity_Creation_Part_1", "Content"),
    ("Modding:Content_Tutorial_Entity_Creation_Part_2", "Content"),
    ("Modding:Content_Tutorial_Further_Recipes","Content"),
    ("Modding:Content_Tutorial_Item_Variants",  "Content"),
    ("Modding:Content_Tutorial_Simple_Block",   "Content"),
    ("Modding:Content_Tutorial_Simple_Item",    "Content"),
    ("Modding:Content_Tutorial_Simple_Recipe",  "Content"),
    ("Modding:Content_Tutorial_Simple_Worldgen","Content"),
    ("Modding:Content_Tutorials_Portal",        "Content"),
    ("Modding:Creating_A_Code_Mod",             "Code"),
    # D
    ("Modding:Debugging_Content",               "Troubleshooting"),
    ("Debugging_Performance_Issues",            "Troubleshooting"),
    ("Modding:Developing_a_Content_Mod",        "Content"),
    # E
    ("Modding:Engine_Portal",                   "Engine"),
    ("Modding:Entity_Behaviors",                "Content"),
    ("Modding:Entity_instance_attributes",      "Content"),
    ("Modding:Entity_Json_Properties",          "AssetTypes"),
    ("Modding:EvolvingNatFloat",                "Code"),
    # G
    ("Modding:Getting_Started",                 "Basics"),
    ("Modding:Glossary",                        "Basics"),
    ("Modding:Grid_Recipes_Guide",              "Content"),
    ("Modding:GUIs",                            "Code"),
    # I
    ("Modding:Inbuilt_ModMaker",                "Basics"),
    ("Modding:InheritFrom",                     "Content"),
    ("Modding:Intermediate_Code_Tutorials",     "Code"),
    ("Modding:Intermediate_Content_Tutorials",  "Content"),
    ("Modding:Item_Json_Properties",            "AssetTypes"),
    # J
    ("Modding:Json_Block_Behaviors",            "AssetTypes"),
    ("Modding:JSON_Patching",                   "Content"),
    ("Modding:JSON_Values",                     "Content"),
    ("Json:block:worldvariantgroups",           "AssetTypes"),
    # M
    ("Modding:Meal_Container",                  "Content"),
    ("Modding:Minidimension",                   "Code"),
    ("Modding:Mod_Packaging",                   "Basics"),
    ("Modding:Mod-Engine_Compatibility",        "Basics"),
    ("Modding:ModConfig",                       "Code"),
    ("Modding:Moddable_Mod",                    "Code"),
    ("Modding:Modding_API_Updates",             "Basics"),
    ("Modding:Modding_Basics_Portal",           "Basics"),
    ("Modding:Modding_Efficiently",             "Basics"),
    ("Modding:Modding_Wiki_Guidelines",         "Basics"),
    ("Modding:Model_Creator_Portal",            "ModelCreator"),
    ("Modding:Modinfo",                         "Basics"),
    ("Modding:Monkey_patching",                 "Code"),
    # N
    ("Modding:NatFloat",                        "Code"),
    ("Modding:Network_API",                     "Code"),
    # O
    ("Modding:Other_Code_Tutorials",            "Code"),
    ("Modding:Other_Content_Tutorials",         "Content"),
    ("Modding:Other_Resources",                 "Other"),
    # P
    ("Modding:Preparing_For_Code_Mods",         "Code"),
    ("Modding:Programming_Languages",           "Basics"),
    # R
    ("Modding:Rendering_API",                   "Engine"),
    # S
    ("Modding:SaveGame_ModData",                "Code"),
    ("Modding:Schematics",                      "Content"),
    ("Modding:Serialization_Formats",           "Code"),
    ("Server_startup_parameters",               "Other"),
    ("Modding:Server-Client_Considerations",    "Code"),
    ("Modding:Setting_up_your_Development_Environment", "Code"),
    ("Modding:Simple_Class_Tutorial",           "Code"),
    ("Modding:Simple_Particles",                "Code"),
    # T
    ("User:Techy/Modding_Resources",            "Other"),
    ("Modding:The_Remapper",                    "Troubleshooting"),
    ("Modding:Theme_Pack",                      "Content"),
    ("Modding:TreeAttribute",                   "Code"),
    ("Modding:Trees",                           "Content"),
    ("Modding:Troubleshooting_Portal",          "Troubleshooting"),
    ("Modding:Types_Of_Mod",                    "Basics"),
    # U
    ("Modding:Using_The_Modding_Wiki",          "Basics"),
    # V
    ("Modding:Variants",                        "Content"),
    ("Modding:VCDBS_format",                    "Other"),
    ("Modding:VS_Model_Creator",                "ModelCreator"),
    ("Modding:VS_Model_Creator_tutorials",      "ModelCreator"),
    ("Modding:VS_Model_Creator/Animation_Intermediate", "ModelCreator"),
    ("VTML",                                    "Other"),
    # W
    ("Modding:World_Access",                    "Code"),
    ("Modding:WorldGen_API",                    "Engine"),
    ("Modding:WorldGen_Concept",                "Engine"),
    ("Modding:WorldGen_Configuration",          "Engine"),
]


def sanitise_filename(title: str) -> str:
    """Turn a wiki page title/path into a safe filename."""
    name = title.replace("Modding:", "").replace("Json:", "Json_").replace("/", "_")
    name = re.sub(r'[<>:"|?*\\]', "_", name)
    return name.strip("_") + ".md"


def fetch_page_markdown(slug: str) -> str | None:
    """Fetch a wiki page and return its main content as Markdown."""
    url = f"{BASE_URL}/{slug}"
    try:
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": "VS-Wiki-Downloader/1.0 (personal archival)"})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract the page title
    title_tag = soup.find("h1", class_="firstHeading") or soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else slug

    # Extract main content div
    content_div = (
        soup.find("div", class_="mw-parser-output")
        or soup.find("div", id="mw-content-text")
    )
    if not content_div:
        print(f"  WARNING: no content found for {slug}")
        return f"# {title}\n\n*Content could not be extracted.*\n"

    # Remove nav boxes, edit links, toc-style tables, etc.
    for tag in content_div.find_all(
        ["div", "table"],
        class_=["toc", "navbox", "mw-editsection", "printfooter",
                "catlinks", "noprint", "sister-project"]
    ):
        tag.decompose()

    # Convert to Markdown
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0          # don't wrap lines
    h.protect_links = True
    h.unicode_snob = True

    md_body = h.handle(str(content_div))

    # Prepend a YAML-ish header with source URL
    header = f"# {title}\n\n> Source: {url}\n\n"
    return header + md_body


def build_toc(results: list[tuple[str, str, str, bool]]) -> str:
    """Build a Markdown table of contents."""
    sections: dict[str, list] = {}
    for slug, folder, filename, ok in results:
        sections.setdefault(folder, []).append((slug, filename, ok))

    lines = ["# Vintage Story Modding Wiki – Offline Archive\n",
             f"Downloaded {sum(1 for *_, ok in results if ok)} / {len(results)} pages.\n"]

    folder_order = ["Basics", "Content", "Code", "AssetTypes",
                    "ModelCreator", "Troubleshooting", "Engine", "Other"]

    for folder in folder_order:
        if folder not in sections:
            continue
        lines.append(f"\n## {folder}\n")
        for slug, filename, ok in sorted(sections[folder]):
            rel_path = f"{folder}/{filename}"
            status = "" if ok else " *(download failed)*"
            display = slug.replace("_", " ")
            lines.append(f"- [{display}]({rel_path}){status}")

    return "\n".join(lines) + "\n"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for folder in set(f for _, f in PAGES):
        (OUTPUT_DIR / folder).mkdir(exist_ok=True)

    results = []
    total = len(PAGES)

    for i, (slug, folder) in enumerate(PAGES, 1):
        filename = sanitise_filename(slug)
        dest = OUTPUT_DIR / folder / filename
        print(f"[{i:3}/{total}] {slug}")

        if dest.exists():
            print("       already downloaded, skipping.")
            results.append((slug, folder, filename, True))
            continue

        md = fetch_page_markdown(slug)
        ok = md is not None
        if ok:
            dest.write_text(md, encoding="utf-8")
            print(f"       saved -> {dest}")
        else:
            results.append((slug, folder, filename, False))
            continue

        results.append((slug, folder, filename, True))
        time.sleep(DELAY)

    # Write index
    index_path = OUTPUT_DIR / "index.md"
    index_path.write_text(build_toc(results), encoding="utf-8")
    print(f"\nDone! Index written to {index_path}")
    success = sum(1 for *_, ok in results if ok)
    print(f"Successfully downloaded {success}/{total} pages into '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()