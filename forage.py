#!/usr/bin/env python3
"""One forage: seed, rumination, query, forage, gift. See NOTEBOOK.md."""

import json
import os
import random
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

from ddgs import DDGS

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(HERE, "prompts")
RUNS_DIR = os.path.join(HERE, "runs")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = "http://" + OLLAMA_HOST
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")

N_SEEDS = 5
SEED_MAX_CHARS = 1500
SEED_MAX_SIZE = 200 * 1024
SEED_MAX_AGE_DAYS = 7
EXCLUDE_SUBSTRINGS = ["systemd", "pip", "npm", "homebrew"]
NOTHING = "[nothing]"

CHOOSE_TEMPLATE = """The bird has these {n} places it could go, out of searching "{query}":

{listing}

The bird goes to exactly one, or none. Third person only. The last line of the reply must be exactly one of:
CHOOSE: <number>
CHOOSE: [nothing]"""

USER_AGENT = "Mozilla/5.0 (compatible; forage-experiment/0.1)"


def read_prompt(name):
    with open(os.path.join(PROMPTS_DIR, name), "r") as f:
        return f.read()


def ollama_generate(prompt, num_predict=120, temperature=0.9):
    url = OLLAMA_HOST.rstrip("/") + "/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,  # qwen3 is a reasoning model; thinking tokens would eat num_predict
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result.get("response", "").strip()


def is_declined(text):
    return text.strip().strip(".").lower() == NOTHING


# --- seed selection -----------------------------------------------------

def is_probably_text(path, sniff_bytes=2048):
    try:
        with open(path, "rb") as f:
            chunk = f.read(sniff_bytes)
    except OSError:
        return False
    if not chunk or b"\x00" in chunk:
        return False
    try:
        chunk.decode("utf-8")
        return True
    except UnicodeDecodeError:
        text = chunk.decode("utf-8", errors="ignore")
        return len(text) > 0.8 * len(chunk)


def find_seed_candidates(dirs):
    now = time.time()
    all_candidates = []
    recent_candidates = []
    seen_real = set()
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, subdirs, files in os.walk(d, onerror=lambda e: None):
            if any(x in root.lower() for x in EXCLUDE_SUBSTRINGS):
                subdirs[:] = []
                continue
            for name in files:
                path = os.path.join(root, name)
                if any(x in path.lower() for x in EXCLUDE_SUBSTRINGS):
                    continue
                try:
                    real = os.path.realpath(path)
                except OSError:
                    continue
                if real in seen_real:
                    continue
                seen_real.add(real)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                if st.st_size == 0 or st.st_size > SEED_MAX_SIZE:
                    continue
                if not is_probably_text(path):
                    continue
                all_candidates.append(path)
                if now - st.st_mtime <= SEED_MAX_AGE_DAYS * 86400:
                    recent_candidates.append(path)
    pool = recent_candidates if recent_candidates else all_candidates
    pool.sort()  # deterministic ordering so a fixed RNG seed reproduces the run
    return pool


def read_seed_text(path):
    with open(path, "r", errors="ignore") as f:
        return f.read(SEED_MAX_CHARS)


# --- search + fetch -------------------------------------------------------
# The raw html.duckduckgo.com/html/ endpoint started throwing an
# image-captcha ("select the squares with a duck") after the first couple
# of requests from this machine's IP -- the ddgs package handles backend
# rotation around that, so we use it instead of hand-rolled scraping.

def search(query, n=5):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=n))
    return [(r.get("title", ""), r.get("href", "")) for r in results]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.chunks.append(data)

    def text(self):
        return " ".join("".join(self.chunks).split())


def fetch_page_text(url, max_chars=3000):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    html = raw.decode("utf-8", errors="ignore")
    extractor = TextExtractor()
    extractor.feed(html)
    return extractor.text()[:max_chars]


# --- the pipeline, one seed at a time --------------------------------------

def build_prior_block(turns):
    if not turns:
        return ""
    labels = ["First", "Second", "Third", "Fourth", "Fifth"]
    lines = ["The bird has already turned this over:\n"]
    for i, t in enumerate(turns):
        lines.append("%s: %s\n" % (labels[i], t))
    return "\n".join(lines)


def run_seed(seed_path, rumination_tpl, query_tpl, gift_tpl):
    record = {
        "seed_path": seed_path,
        "seed_excerpt": None,
        "rumination_turns": [],
        "ended_at": None,
        "query": None,
        "search_results": [],
        "chosen": None,
        "choose_raw": None,
        "gift": NOTHING,
        "error": None,
    }
    try:
        seed_text = read_seed_text(seed_path)
        record["seed_excerpt"] = seed_text

        # rumination: three turns, any of which may end the seed
        turns = []
        for _ in range(3):
            prompt = rumination_tpl.format(seed=seed_text, prior=build_prior_block(turns))
            turn = ollama_generate(prompt, num_predict=160, temperature=0.9)
            turns.append(turn)
            record["rumination_turns"] = turns
            if is_declined(turn):
                record["ended_at"] = "rumination"
                return record

        # query
        rumination_block = "\n\n".join(
            "%s: %s" % (label, t)
            for label, t in zip(["First", "Second", "Third"], turns)
        )
        query_prompt = query_tpl.format(seed=seed_text, rumination=rumination_block)
        query = ollama_generate(query_prompt, num_predict=20, temperature=0.9)
        record["query"] = query
        if is_declined(query):
            record["ended_at"] = "query"
            return record

        # forage: search, then let the bird choose a result
        results = search(query, n=5)
        record["search_results"] = results
        if not results:
            record["ended_at"] = "forage-empty"
            return record

        listing = "\n".join(
            "%d. %s — %s" % (i + 1, title or "(untitled)", url)
            for i, (title, url) in enumerate(results)
        )
        choose_prompt = CHOOSE_TEMPLATE.format(n=len(results), query=query, listing=listing)
        choose_raw = ollama_generate(choose_prompt, num_predict=200, temperature=0.9)
        record["choose_raw"] = choose_raw

        chosen_index = None
        for line in reversed(choose_raw.splitlines()):
            line = line.strip()
            if line.upper().startswith("CHOOSE:"):
                value = line.split(":", 1)[1].strip()
                if value.strip("[]").lower() == "nothing":
                    chosen_index = None
                else:
                    try:
                        chosen_index = int("".join(c for c in value if c.isdigit()))
                    except ValueError:
                        chosen_index = None
                break

        if not chosen_index or not (1 <= chosen_index <= len(results)):
            record["ended_at"] = "choose"
            return record

        record["chosen"] = results[chosen_index - 1]
        page_url = record["chosen"][1]

        try:
            page_text = fetch_page_text(page_url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            record["error"] = "fetch failed: %s" % e
            record["ended_at"] = "fetch-error"
            return record

        if not page_text:
            record["ended_at"] = "fetch-empty"
            return record

        # gift
        gift_prompt = gift_tpl.format(page=page_text)
        gift = ollama_generate(gift_prompt, num_predict=60, temperature=0.9)
        record["gift"] = gift if gift else NOTHING
        return record

    except Exception as e:
        record["error"] = "%s: %s" % (type(e).__name__, e)
        record["ended_at"] = record["ended_at"] or "error"
        return record


# --- run + record -----------------------------------------------------------

def write_notebook(path, run_meta, records):
    with open(path, "w") as f:
        f.write("# Forage run %s\n\n" % run_meta["timestamp"])
        f.write("- model: %s\n" % run_meta["model"])
        f.write("- ollama host: %s\n" % run_meta["host"])
        f.write("- rng seed: %s\n" % run_meta["rng_seed"])
        f.write("- wall time: %.1fs\n\n" % run_meta["wall_time"])

        f.write("## Prompts at run time\n\n")
        for name, content in run_meta["prompts"].items():
            f.write("### %s\n\n```\n%s\n```\n\n" % (name, content))

        ended = [r for r in records if r["ended_at"]]
        f.write("## Seeds that ended with nothing\n\n")
        if ended:
            for r in ended:
                f.write("- %s — ended at `%s`%s\n" % (
                    r["seed_path"], r["ended_at"],
                    " (%s)" % r["error"] if r["error"] else "",
                ))
        else:
            f.write("(none — every seed reached a gift)\n")
        f.write("\n")

        for i, r in enumerate(records, 1):
            f.write("## Seed %d: %s\n\n" % (i, r["seed_path"]))
            f.write("### Seed excerpt\n\n```\n%s\n```\n\n" % r["seed_excerpt"])

            f.write("### Rumination\n\n")
            for j, turn in enumerate(r["rumination_turns"], 1):
                f.write("Turn %d: %s\n\n" % (j, turn))

            if r["query"] is not None:
                f.write("### Query\n\n`%s`\n\n" % r["query"])

            if r["search_results"]:
                f.write("### Search results\n\n")
                for k, (title, url) in enumerate(r["search_results"], 1):
                    f.write("%d. %s — %s\n" % (k, title or "(untitled)", url))
                f.write("\n")

            if r["choose_raw"] is not None:
                f.write("### Choice (raw)\n\n```\n%s\n```\n\n" % r["choose_raw"])
                if r["chosen"]:
                    f.write("Chosen: %s — %s\n\n" % r["chosen"])

            f.write("### Gift\n\n%s\n\n" % r["gift"])
            if r["ended_at"]:
                f.write("(ended at `%s`%s)\n\n" % (
                    r["ended_at"], " — %s" % r["error"] if r["error"] else "",
                ))
            f.write("---\n\n")


def write_ledge_and_key(ledge_path, key_path, records, rng):
    entries = list(enumerate(records, 1))
    rng.shuffle(entries)
    with open(ledge_path, "w") as lf, open(key_path, "w") as kf:
        for n, (_, r) in enumerate(entries, 1):
            lf.write("%d. %s\n" % (n, r["gift"]))
            kf.write("%d. %s\n" % (n, r["seed_path"]))


def main():
    started = time.time()
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    rng_seed = os.environ.get("FORAGE_SEED")
    if rng_seed is None:
        rng_seed = int.from_bytes(os.urandom(8), "big")
    else:
        rng_seed = int(rng_seed)
    print("RNG seed: %d" % rng_seed)
    rng = random.Random(rng_seed)

    rumination_tpl = read_prompt("rumination.txt")
    query_tpl = read_prompt("query.txt")
    gift_tpl = read_prompt("gift.txt")

    seed_dirs = ["/tmp"]
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        seed_dirs.append(tmpdir)
    candidates = find_seed_candidates(seed_dirs)
    if len(candidates) < N_SEEDS:
        print("only found %d usable seed candidates, need %d" % (len(candidates), N_SEEDS), file=sys.stderr)
        sys.exit(1)

    chosen_seeds = []
    pool = list(candidates)
    for _ in range(N_SEEDS):
        pick = rng.choice(pool)
        pool.remove(pick)
        chosen_seeds.append(pick)

    records = []
    for seed_path in chosen_seeds:
        print("foraging from %s" % seed_path)
        records.append(run_seed(seed_path, rumination_tpl, query_tpl, gift_tpl))

    wall_time = time.time() - started

    run_dir = os.path.join(RUNS_DIR, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    run_meta = {
        "timestamp": timestamp,
        "model": OLLAMA_MODEL,
        "host": OLLAMA_HOST,
        "rng_seed": rng_seed,
        "wall_time": wall_time,
        "prompts": {
            "rumination.txt": rumination_tpl,
            "query.txt": query_tpl,
            "gift.txt": gift_tpl,
        },
    }
    write_notebook(os.path.join(run_dir, "notebook.md"), run_meta, records)
    write_ledge_and_key(
        os.path.join(run_dir, "ledge.md"),
        os.path.join(run_dir, "key.md"),
        records,
        rng,
    )
    print("run written to %s" % run_dir)


if __name__ == "__main__":
    main()
