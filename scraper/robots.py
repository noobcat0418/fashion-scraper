"""A small robots.txt parser with wildcard support.

Python's urllib.robotparser ignores `*` and `$` inside paths, so a rule like `Disallow: /*.json`
would silently read as "allowed". This follows Google's rules instead: the longest matching
pattern wins, and Allow wins a tie.
"""
import re


class Robots:
    def __init__(self, text: str, agent: str):
        groups, current, last_was_agent = [], None, False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = {"agents": [], "rules": [], "delay": None}
                    groups.append(current)
                current["agents"].append(value.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if current is None:
                continue
            if key in ("allow", "disallow") and value:  # an empty Disallow means "allow everything"
                current["rules"].append((key == "allow", value))
            elif key == "crawl-delay":
                try:
                    current["delay"] = float(value)
                except ValueError:
                    pass

        # A group naming us specifically beats the catch-all "*" group.
        token = agent.lower()
        specific = [g for g in groups if any(a != "*" and a in token for a in g["agents"])]
        chosen = specific or [g for g in groups if "*" in g["agents"]]
        self.rules = [rule for g in chosen for rule in g["rules"]]
        delays = [g["delay"] for g in chosen if g["delay"] is not None]
        self.crawl_delay = max(delays) if delays else None
        self.blocked_everything = False

    @classmethod
    def disallow_all(cls, reason: str) -> "Robots":
        robots = cls("", "")
        robots.blocked_everything = reason
        return robots

    def allowed(self, path: str) -> bool:
        if self.blocked_everything:
            return False
        best = None
        for allow, pattern in self.rules:
            if _matches(pattern, path):
                if best is None or len(pattern) > len(best[1]) or (len(pattern) == len(best[1]) and allow):
                    best = (allow, pattern)
        return True if best is None else best[0]


def _matches(pattern: str, path: str) -> bool:
    regex = re.escape(pattern).replace(r"\*", ".*")
    if regex.endswith(r"\$"):
        regex = regex[:-2] + "$"
    return re.match(regex, path) is not None
