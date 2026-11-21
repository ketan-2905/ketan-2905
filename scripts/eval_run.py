#!/usr/bin/env python3
"""Re-runs the 'eval' in the README header against live GitHub data.

Rewrites everything between <!--EVAL:START--> and <!--EVAL:END--> so the
console block on the profile reports real numbers instead of decoration.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

USER = os.environ.get("PROFILE_USER") or "ketan-2905"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
START, END = "<!--EVAL:START-->", "<!--EVAL:END-->"


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-eval-run",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def collect():
    repos, page = [], 1
    while page <= 5:
        batch = api(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        repos.extend(batch)
        page += 1

    own = [r for r in repos if not r.get("fork")]
    langs = Counter(r["language"] for r in own if r.get("language"))
    stars = sum(r.get("stargazers_count", 0) for r in own)

    pushes = [r["pushed_at"] for r in own if r.get("pushed_at")]
    latest = max(pushes) if pushes else None
    if latest:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(
            latest.replace("Z", "+00:00")
        )
        hours = int(delta.total_seconds() // 3600)
        freshness = f"{hours}h ago" if hours < 48 else f"{hours // 24}d ago"
    else:
        freshness = "unknown"

    top = ", ".join(f"{k} {v}" for k, v in langs.most_common(4))
    return {
        "repos": len(own),
        "stars": stars,
        "langs": len(langs),
        "top": top,
        "fresh": freshness,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def render(d):
    bar = "█" * 28
    return f"""```console
$ eval-run --subject "Ketan Gaikwad" --live --explain

  sampling evidence ...... {d['repos']} public repos · {d['langs']} languages · 6 hackathon wins
  language mix ........... {d['top']}
  last push .............. {d['fresh']}
  judging ................ {bar} 100%

  VERDICT   builds LLM systems that can prove they were right
  CONF      0.94
  ABSTAIN   when the sources don't support an answer

  evaluated at {d['ts']} · this block is regenerated daily by CI
```"""


def main():
    try:
        data = collect()
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as e:
        print(f"eval-run: could not reach GitHub ({e}); leaving README untouched")
        return 0

    src = open(README, encoding="utf-8").read()
    if START not in src or END not in src:
        print("eval-run: markers missing; nothing to do")
        return 1

    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        f"{START}\n{render(data)}\n{END}",
        src,
        flags=re.S,
    )
    if new == src:
        print("eval-run: no change")
        return 0
    open(README, "w", encoding="utf-8").write(new)
    print(f"eval-run: updated — {data['repos']} repos, {data['langs']} langs, {data['stars']} stars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
