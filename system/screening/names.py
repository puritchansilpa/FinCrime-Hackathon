"""Name agreement (POLICY.md principle 8).  [Workstream B]

Two parts match when they are identical, are listed together in name_variants.json,
are written together or apart (Abdulsalam ~ Abdul Salam, one part covering both), or
differ by at most 1 edit for parts of 4-6 letters and 2 for longer ones (the shorter
part's length decides; parts under 4 letters must be identical; a swap is 2 edits).

Names agree when at least two parts match, or every part of the shorter name matches.
"""

import json
from dataclasses import dataclass, field
from itertools import permutations
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from .normalize import fold, name_parts

DEFAULT_LEGAL_FORMS = (
    "ab", "ag", "as", "asa", "bv", "co", "company", "corp", "corporation", "gmbh", "inc", "kg",
    "limited", "llc", "llp", "lp", "ltd", "na", "nv", "oy", "oyj", "plc", "sa", "sarl", "sas",
    "se", "sf", "sl", "spa", "srl",
)


@dataclass
class Variants:
    """Given-name variant groups and company legal forms from name_variants.json."""
    groups: List[List[str]] = field(default_factory=list)
    legal_forms: Tuple[str, ...] = DEFAULT_LEGAL_FORMS
    _index: Dict[str, Set[int]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._index = {}
        for gi, group in enumerate(self.groups):
            for name in group:
                for key in name_parts(name) or [fold(name).lower()]:
                    self._index.setdefault(key, set()).add(gi)
        self.legal_forms = tuple(fold(f).lower().replace(".", "").strip() for f in self.legal_forms if f)

    def same_group(self, a: str, b: str) -> bool:
        ga = self._index.get(a)
        return bool(ga and ga & self._index.get(b, set()))

    @classmethod
    def from_obj(cls, obj) -> "Variants":
        """Accepts the layouts we have seen or can expect:
        {"name_variants": [[...]], "company_legal_forms": [...]}, {"groups": ...},
        {"muhammad": ["mohammed", ...]}, or a plain list of groups."""
        groups, legal = [], None
        if isinstance(obj, list):
            groups = obj
        elif isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if "legal" in kl or "form" in kl or "suffix" in kl:
                    legal = v
                elif isinstance(v, list) and v and all(isinstance(x, list) for x in v):
                    groups.extend(v)
                elif isinstance(v, list) and all(isinstance(x, str) for x in v):
                    if "variant" in kl or "group" in kl or "name" in kl:
                        groups.append(v)
                    else:
                        groups.append([k] + v)           # {"muhammad": ["mohammed", ...]}
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        if isinstance(vv, list):
                            groups.append([kk] + [x for x in vv if isinstance(x, str)])
        groups = [[str(x) for x in g if isinstance(x, str)] for g in groups if isinstance(g, list)]
        if isinstance(legal, str):
            legal = [x.strip() for x in legal.replace(";", ",").split(",")]
        return cls(groups=[g for g in groups if g], legal_forms=tuple(legal or DEFAULT_LEGAL_FORMS))

    @classmethod
    def load(cls, path) -> "Variants":
        p = Path(path)
        if p.is_dir():
            p = p / "name_variants.json"
        if not p.exists():
            return cls()
        with p.open(encoding="utf-8") as f:
            return cls.from_obj(json.load(f))


# ---------------------------------------------------------------------------
# Part matching
# ---------------------------------------------------------------------------

def edit_distance(a: str, b: str, limit: int = 99) -> int:
    """Levenshtein distance (insert, delete, substitute; a swap costs 2). Stops early past `limit`."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            best = min(best, v)
        if best > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def allowed_edits(a: str, b: str) -> int:
    n = min(len(a), len(b))
    if n < 4:
        return 0
    if n <= 6:
        return 1
    return 2


def parts_match(a: str, b: str, variants: Optional[Variants] = None) -> bool:
    if a == b:
        return True
    if variants is not None and variants.same_group(a, b):
        return True
    k = allowed_edits(a, b)
    return k > 0 and edit_distance(a, b, k) <= k


# ---------------------------------------------------------------------------
# Name agreement
# ---------------------------------------------------------------------------

Edge = Tuple[FrozenSet[int], FrozenSet[int]]


def _edges(A: Sequence[str], B: Sequence[str], variants: Optional[Variants]) -> Tuple[List[Edge], List[Edge]]:
    singles, joins = [], []
    for i, a in enumerate(A):
        for j, b in enumerate(B):
            if parts_match(a, b, variants):
                singles.append((frozenset([i]), frozenset([j])))
    # written together or apart: one part of one name = two parts of the other, joined
    for i, a in enumerate(A):
        for j1, j2 in permutations(range(len(B)), 2):
            if parts_match(a, B[j1] + B[j2], variants):
                joins.append((frozenset([i]), frozenset([j1, j2])))
    for j, b in enumerate(B):
        for i1, i2 in permutations(range(len(A)), 2):
            if parts_match(b, A[i1] + A[i2], variants):
                joins.append((frozenset([i1, i2]), frozenset([j])))
    # a joined pair in either order is the same edge
    return singles, sorted(set(joins), key=lambda e: (sorted(e[0]), sorted(e[1])))


def _max_single_matching(singles: List[Edge], usedA: Set[int], usedB: Set[int]) -> List[Tuple[int, int]]:
    adj: Dict[int, List[int]] = {}
    for ea, eb in singles:
        (i,), (j,) = tuple(ea), tuple(eb)
        if i in usedA or j in usedB:
            continue
        adj.setdefault(i, []).append(j)
    match_b: Dict[int, int] = {}

    def augment(i, seen):
        for j in adj.get(i, []):
            if j in seen:
                continue
            seen.add(j)
            if j not in match_b or augment(match_b[j], seen):
                match_b[j] = i
                return True
        return False

    for i in sorted(adj):
        augment(i, set())
    return sorted((i, j) for j, i in match_b.items())


@dataclass
class NameMatch:
    agree: bool
    matches: int
    covered_a: FrozenSet[int]
    covered_b: FrozenSet[int]
    parts_a: List[str]
    parts_b: List[str]


def match_parts(A: Sequence[str], B: Sequence[str], variants: Optional[Variants] = None) -> NameMatch:
    """Best matching between two part lists; each part is used at most once."""
    A, B = list(A), list(B)
    if not A or not B:
        return NameMatch(False, 0, frozenset(), frozenset(), A, B)
    singles, joins = _edges(A, B, variants)
    joins = joins[:12]  # joins are rare; cap the search
    best = None

    def consider(chosen_joins):
        nonlocal best
        usedA = set().union(*[e[0] for e in chosen_joins]) if chosen_joins else set()
        usedB = set().union(*[e[1] for e in chosen_joins]) if chosen_joins else set()
        pairs = _max_single_matching(singles, usedA, usedB)
        ca = frozenset(usedA | {i for i, _ in pairs})
        cb = frozenset(usedB | {j for _, j in pairs})
        n = len(chosen_joins) + len(pairs)
        key = (n, len(ca) + len(cb))
        if best is None or key > best[0]:
            best = (key, n, ca, cb)

    def search(k, chosen, usedA, usedB):
        if k == len(joins):
            consider(chosen)
            return
        search(k + 1, chosen, usedA, usedB)
        ea, eb = joins[k]
        if not (ea & usedA) and not (eb & usedB):
            search(k + 1, chosen + [joins[k]], usedA | ea, usedB | eb)

    search(0, [], frozenset(), frozenset())
    _, n, ca, cb = best
    short_full = (
        (len(A) <= len(B) and len(ca) == len(A)) or
        (len(B) <= len(A) and len(cb) == len(B))
    )
    return NameMatch(n >= 2 or short_full, n, ca, cb, A, B)


def names_agree(a: str, b: str, variants: Optional[Variants] = None, is_company: bool = False) -> bool:
    legal = variants.legal_forms if variants else DEFAULT_LEGAL_FORMS
    return match_parts(name_parts(a, is_company, legal), name_parts(b, is_company, legal), variants).agree


def real_parts(name: str, is_company: bool = False, variants: Optional[Variants] = None) -> List[str]:
    legal = variants.legal_forms if variants else DEFAULT_LEGAL_FORMS
    return name_parts(name, is_company, legal)


def first_agreeing(customer_names: Iterable[str], hit_names: Iterable[str],
                   variants: Optional[Variants] = None, is_company: bool = False) -> Optional[Tuple[str, str]]:
    """First (customer_name, hit_name) pair that agrees, in the given order; None if none."""
    hit_names = list(hit_names)
    for cn in customer_names:
        for hn in hit_names:
            if names_agree(cn, hn, variants, is_company):
                return cn, hn
    return None
