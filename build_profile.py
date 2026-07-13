"""
Regenerates dark_mode.svg and light_mode.svg with live GitHub stats.

Runs in GitHub Actions (or locally). Uses ACCESS_TOKEN if set (sees private
repos), otherwise GITHUB_TOKEN (public repos only).

Layout inspired by Andrew6rant/Andrew6rant.
"""
import datetime
import os
import time
import urllib.request
import json

USER = "JafarBanar"
TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ["GITHUB_TOKEN"]
WIDTH = 60  # visible characters per info line

DARK = {
    "bg": "#161b22", "fg": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
    "add": "#3fb950", "del": "#f85149", "cc": "#616e7f",
}
LIGHT = {
    "bg": "#f6f8fa", "fg": "#24292f", "key": "#953800", "value": "#0a3069",
    "add": "#1a7f37", "del": "#cf222e", "cc": "#c2cfde",
}


def api(url, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"bearer {TOKEN}",
                 "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as r:
        if r.status == 202:
            return None
        return json.loads(r.read().decode())


def graphql(query):
    return api("https://api.github.com/graphql", {"query": query})["data"]


def fetch_stats():
    d = graphql(f'''
    {{
      user(login: "{USER}") {{
        createdAt
        followers {{ totalCount }}
        repositories(first: 100, ownerAffiliations: OWNER) {{
          totalCount
          nodes {{ nameWithOwner stargazerCount }}
        }}
        repositoriesContributedTo(first: 1,
          contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) {{ totalCount }}
        contributionsCollection {{ contributionYears }}
      }}
    }}''')["user"]

    commits = 0
    for y in d["contributionsCollection"]["contributionYears"]:
        c = graphql(f'''
        {{
          user(login: "{USER}") {{
            contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{
              totalCommitContributions
            }}
          }}
        }}''')["user"]["contributionsCollection"]["totalCommitContributions"]
        commits += c

    added = deleted = 0
    for repo in d["repositories"]["nodes"]:
        url = f"https://api.github.com/repos/{repo['nameWithOwner']}/stats/contributors"
        stats = None
        for _ in range(5):
            try:
                stats = api(url)
            except Exception:
                stats = None
            if stats is not None:
                break
            time.sleep(3)
        for contributor in stats or []:
            if contributor["author"] and contributor["author"]["login"] == USER:
                for week in contributor["weeks"]:
                    added += week["a"]
                    deleted += week["d"]

    return {
        "created": datetime.datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00")),
        "followers": d["followers"]["totalCount"],
        "repos": d["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in d["repositories"]["nodes"]),
        "contributed": d["repositoriesContributedTo"]["totalCount"],
        "commits": commits,
        "added": added,
        "deleted": deleted,
    }


def uptime(created):
    now = datetime.datetime.now(datetime.timezone.utc)
    years = now.year - created.year
    months = now.month - created.month
    days = now.day - created.day
    if days < 0:
        months -= 1
        prev = (now.replace(day=1) - datetime.timedelta(days=1)).day
        days += prev
    if months < 0:
        years -= 1
        months += 12
    return f"{years} years, {months} months, {days} days"


# ---- SVG assembly ----------------------------------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def seg(text, cls=None):
    return (text, cls)


def kv(keys, value):
    """'. Key.Sub: .... value' padded to WIDTH visible chars."""
    segs = [seg(". ", "cc")]
    length = 2
    for i, k in enumerate(keys):
        if i:
            segs.append(seg("."))
            length += 1
        segs.append(seg(k, "key"))
        length += len(k)
    segs.append(seg(":"))
    length += 1
    dots = WIDTH - length - len(value) - 2
    segs.append(seg(" " + "." * max(dots, 2) + " ", "cc"))
    segs.append(seg(value, "value"))
    return segs


def header(text):
    dashes = WIDTH - len(text) - 3
    return [seg(text), seg(" -" + "—" * max(dashes, 3) + "-")]


def two_col(key1, val1, extra, key2, val2):
    """'. K1: ... v1 {Extra: n} | K2: ... v2' padded to WIDTH."""
    extra_len = sum(len(x) for x in extra) + 2 if extra else 0  # + ': '
    fixed = (2 + len(key1) + 1 + 2 + len(val1) + extra_len
             + 3 + len(key2) + 1 + 2 + len(val2))
    dots1 = max((WIDTH - fixed) // 2, 2)
    dots2 = max(WIDTH - fixed - dots1, 2)
    segs = [seg(". ", "cc"), seg(key1, "key"), seg(":"),
            seg(" " + "." * dots1 + " ", "cc"), seg(val1, "value")]
    if extra:
        segs.append(seg(extra[0]))
        segs.append(seg(extra[1], "key"))
        segs.append(seg(": "))
        segs.append(seg(extra[2], "value"))
        segs.append(seg(extra[3]))
    segs += [seg(" | "), seg(key2, "key"), seg(":"),
             seg(" " + "." * dots2 + " ", "cc"), seg(val2, "value")]
    return segs


def loc_line(net, added, deleted):
    prefix = ". Lines of Code:"
    tail = f"{net} ({added}++, {deleted}--)"
    dots = WIDTH - len(prefix) - len(tail) - 2
    return [seg(". ", "cc"), seg("Lines of Code", "key"), seg(":"),
            seg(" " + "." * max(dots, 1) + " ", "cc"),
            seg(net, "value"), seg(" ("),
            seg(added, "add"), seg("++", "add"), seg(", "),
            seg(deleted, "del"), seg("--", "del"), seg(")")]


def render(theme, ascii_lines, panel):
    out = []
    out.append("<?xml version='1.0' encoding='UTF-8'?>")
    out.append('<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="985px" height="530px" font-size="16px">')
    out.append(f'''<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {theme["key"]};}}
.value {{fill: {theme["value"]};}}
.addColor {{fill: {theme["add"]};}}
.delColor {{fill: {theme["del"]};}}
.cc {{fill: {theme["cc"]};}}
text, tspan {{white-space: pre;}}
</style>''')
    out.append(f'<rect width="985px" height="530px" fill="{theme["bg"]}" rx="15"/>')

    # ascii portrait at 10px (denser grid than the 16px info panel),
    # vertically centered in the 500px-tall art area
    step = 12.5
    start = 22 + (500 - len(ascii_lines) * step) / 2
    out.append(f'<text x="15" y="{start}" fill="{theme["fg"]}" class="ascii" font-size="10px">')
    for i, line in enumerate(ascii_lines):
        out.append(f'<tspan x="15" y="{start + i * step}">{esc(line)}</tspan>')
    out.append("</text>")

    cls_map = {"key": "key", "value": "value", "add": "addColor", "del": "delColor", "cc": "cc"}
    out.append(f'<text x="390" y="30" fill="{theme["fg"]}">')
    for y, segs in panel:
        parts = ""
        for text, cls in segs:
            c = f' class="{cls_map[cls]}"' if cls else ""
            parts += f"<tspan{c}>{esc(text)}</tspan>"
        out.append(f'<tspan x="390" y="{y}">{parts}</tspan>')
    out.append("</text>")
    out.append("</svg>")
    return "\n".join(out)


def main():
    s = fetch_stats()
    with open("ascii_portrait.txt") as f:
        ascii_lines = f.read().splitlines()

    fmt = lambda n: f"{n:,}"
    panel = [
        (30, header(f"jafar@banar")),
        (50, kv(["OS"], "macOS, Linux, Windows")),
        (70, kv(["Uptime"], uptime(s["created"]))),
        (90, kv(["Host"], "Volvo Cars (via Sigma Embedded)")),
        (110, kv(["Kernel"], "Senior Data Engineer, AI & Perception")),
        (130, kv(["IDE"], "VSCode, Claude Code, MATLAB")),
        (150, [seg(". ", "cc")]),
        (170, kv(["Languages", "Programming"], "Python, SQL, C/C++, Go, MATLAB")),
        (190, kv(["Languages", "Computer"], "Bash, LaTeX, YAML, JSON")),
        (210, kv(["Languages", "Real"], "Persian, English, Swedish")),
        (230, [seg(". ", "cc")]),
        (250, kv(["PhD", "Universities"], "Chalmers & TU Eindhoven (dual)")),
        (270, kv(["PhD", "Focus"], "5G/6G Sync, Distributed MIMO, Radar")),
        (290, [seg(". ", "cc")]),
        (310, header("- Contact")),
        (330, kv(["Email", "Personal"], "jaafar.banar@gmail.com")),
        (350, kv(["LinkedIn"], "jafarbanar")),
        (370, kv(["GitHub"], "JafarBanar")),
        (390, kv(["Location"], "Gothenburg, Sweden")),
        (450, header("- GitHub Stats")),
        (470, two_col("Repos", str(s["repos"]),
                      (" {", "Contributed", str(s["contributed"]), "}"),
                      "Stars", fmt(s["stars"]))),
        (490, two_col("Commits", fmt(s["commits"]), None,
                      "Followers", fmt(s["followers"]))),
        (510, loc_line(fmt(s["added"] - s["deleted"]), fmt(s["added"]), fmt(s["deleted"]))),
    ]

    for name, theme in (("dark_mode.svg", DARK), ("light_mode.svg", LIGHT)):
        with open(name, "w") as f:
            f.write(render(theme, ascii_lines, panel))
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
