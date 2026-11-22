"""Logique pure de Renshū : correction, barèmes, révision espacée, format des données.

Aucune dépendance à Qt : tout est testé dans tests/test_core.py.
Reprend exactement les règles de la version web (js/grading.js, js/srs.js, js/model.js).
"""
from __future__ import annotations

import html
import math
import random
import re
import time

DAY = 24 * 3600  # secondes

# ---------------------------------------------------------------- correction

# Statut de chaque proposition après correction :
#   hit      bonne réponse cochée            (vert)
#   miss     bonne réponse oubliée           (pointillés verts)
#   wrong    mauvaise réponse cochée         (rouge)
#   doubtful affirmation douteuse            (orange, ne compte ni pour ni contre)
#   neutral  mauvaise réponse non cochée


def grade_question(question: dict, checked) -> dict:
    checked = set(checked)
    hits = misses = wrongs = 0
    statuses = []
    for i, o in enumerate(question["options"]):
        is_checked = i in checked
        if o.get("doubtful"):
            statuses.append("doubtful")
        elif o.get("correct") and is_checked:
            hits += 1
            statuses.append("hit")
        elif o.get("correct"):
            misses += 1
            statuses.append("miss")
        elif is_checked:
            wrongs += 1
            statuses.append("wrong")
        else:
            statuses.append("neutral")
    errors = misses + wrongs
    return {"statuses": statuses, "errors": errors, "hits": hits,
            "misses": misses, "wrongs": wrongs, "ok": errors == 0}


SCHEMES = {
    "tout-ou-rien": {"type": "all-or-nothing", "points": 1,
                     "label": "Tout ou rien (+1 si entièrement juste, 0 sinon)"},
    "penalite": {"type": "penalty", "points": 1, "penalty": 0.25, "floor": 0,
                 "label": "Pénalité par case fausse (−0,25 par erreur, plancher 0)"},
    "penalite-negatif": {"type": "penalty", "points": 1, "penalty": 0.5, "floor": -1,
                         "label": "Pénalité par case, note négative possible (−0,5 par erreur, plancher −1)"},
}


def round2(x: float) -> float:
    """Arrondi au centième comme Math.round en JS (0,5 vers le haut)."""
    return math.floor(x * 100 + 0.5) / 100


def score_question(result: dict, scheme: dict) -> float:
    points = scheme.get("points", 1)
    if scheme["type"] == "all-or-nothing":
        return points if result["ok"] else 0
    if scheme["type"] == "penalty":
        raw = points - scheme.get("penalty", 0.25) * result["errors"]
        return round2(max(scheme.get("floor", 0), min(points, raw)))
    raise ValueError("Barème inconnu : " + str(scheme["type"]))


def score_quiz(results: list, scheme: dict) -> dict:
    points = scheme.get("points", 1)
    max_ = len(results) * points
    total = round2(sum(score_question(r, scheme) for r in results))
    ok_count = sum(1 for r in results if r["ok"])
    on20 = round2(max(0, total) / max_ * 20) if max_ else 0
    return {"total": total, "max": max_, "ok_count": ok_count,
            "count": len(results), "on20": on20}


# ---------------------------------------------------------- révision espacée

INTERVALS_DAYS = [0, 0, 1, 3, 7, 16]  # index = boîte (1..5)


def empty_card() -> dict:
    return {"box": 0, "due": 0, "seen": 0, "wrong": 0, "streak": 0, "last": 0}


def review(card: dict | None, ok: bool, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    c = {**empty_card(), **(card or {})}
    c["seen"] += 1
    c["last"] = now
    if ok:
        c["box"] = min(5, max(1, c["box"]) + 1)
        c["streak"] += 1
    else:
        c["box"] = 1
        c["wrong"] += 1
        c["streak"] = 0
    c["due"] = now + INTERVALS_DAYS[c["box"]] * DAY
    return c


def priority(card: dict | None, now: float | None = None) -> int:
    """0 ratée à revoir, 1 à revoir, 2 jamais vue, 3 pas encore à revoir."""
    now = time.time() if now is None else now
    if not card or not card.get("seen"):
        return 2
    if card["due"] <= now:
        return 0 if card["box"] <= 1 else 1
    return 3


def pick(pool: list, stats: dict, n: int, prioritize: bool = True,
         now: float | None = None, rng: random.Random | None = None) -> list:
    rng = rng or random.Random()
    now = time.time() if now is None else now
    shuffled = pool[:]
    rng.shuffle(shuffled)
    if not prioritize:
        return shuffled[:n]
    keyed = []
    for i, q in enumerate(shuffled):
        c = stats.get(q["id"])
        p = priority(c, now)
        box = (c or {}).get("box", 0)
        due = (c or {}).get("due", 0)
        keyed.append(((p, box if p <= 1 else 0, due if p <= 1 else 0, i), q))
    keyed.sort(key=lambda k: k[0])
    chosen = [q for _, q in keyed[:n]]
    rng.shuffle(chosen)  # ne pas présenter les ratées en tête
    return chosen


def summary(questions: list, stats: dict, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    s = {"total": len(questions), "seen": 0, "mastered": 0, "to_review": 0,
         "boxes": [0] * 6}
    for q in questions:
        c = stats.get(q["id"])
        seen = bool(c and c.get("seen"))
        s["boxes"][c["box"] if seen else 0] += 1
        if seen:
            s["seen"] += 1
            if c["due"] <= now:
                s["to_review"] += 1
        if c and c.get("box", 0) >= 4:
            s["mastered"] += 1
    return s


def chapter_stats(questions: list, stats: dict) -> dict:
    """Réussite par chapitre : {chapitre: {seen, answers, wrong, rate}} (rate = None si jamais vu)."""
    out: dict = {}
    for q in questions:
        ch = out.setdefault(q["chapter"], {"questions": 0, "seen": 0, "answers": 0, "wrong": 0})
        ch["questions"] += 1
        c = stats.get(q["id"])
        if c and c.get("seen"):
            ch["seen"] += 1
            ch["answers"] += c["seen"]
            ch["wrong"] += c["wrong"]
    for ch in out.values():
        ch["rate"] = (1 - ch["wrong"] / ch["answers"]) if ch["answers"] else None
    return out


def weakest(questions: list, stats: dict, n: int = 5) -> list:
    """Questions les plus ratées (au moins une erreur), de la pire à la moins pire."""
    scored = []
    for q in questions:
        c = stats.get(q["id"])
        if c and c.get("wrong"):
            scored.append((-(c["wrong"] / c["seen"]), -c["wrong"], q["id"], q))
    scored.sort(key=lambda t: t[:3])
    return [t[3] for t in scored[:n]]


def by_chapter(questions: list, results: list) -> list:
    """Bilan d'une copie par chapitre : [(chapitre, justes, total)] trié du plus faible au plus fort."""
    acc: dict = {}
    for q, r in zip(questions, results):
        ok, n = acc.get(q["chapter"], (0, 0))
        acc[q["chapter"]] = (ok + (1 if r["ok"] else 0), n + 1)
    return sorted(((ch, ok, n) for ch, (ok, n) in acc.items()), key=lambda t: (t[1] / t[2], t[0]))


# ------------------------------------------------------------------ données

_ALLOWED = re.compile(r"&lt;(/?)(code|b|i|sup|sub|em|strong)&gt;|&lt;br\s*/?&gt;", re.I)


def safe_html(s) -> str:
    """Échappe tout le HTML sauf <code> <b> <i> <sup> <sub> <em> <strong> <br>."""
    esc = html.escape(str(s or ""), quote=False)
    esc = re.sub(r"&amp;(#?\w+);", r"&\1;", esc)  # garder les entités déjà écrites

    def repl(m):
        if m.group(2):
            tag = m.group(2).lower()
            if tag == "code":
                return "<code>" if not m.group(1) else "</code>"
            return f"<{m.group(1)}{tag}>"
        return "<br>"
    return _ALLOWED.sub(repl, esc)


def strip_html(s) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", str(s or "")))


def blank_option() -> dict:
    return {"text": "", "correct": False, "doubtful": False, "explanation": ""}


def next_id(questions: list) -> str:
    n = 0
    for q in questions:
        m = re.fullmatch(r"q(\d+)", str(q.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return f"q{n + 1:03d}"


def normalize_db(raw: dict) -> dict:
    """Valide et complète un fichier de questions. Les champs inconnus sont conservés."""
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), list):
        raise ValueError("Fichier invalide : il faut un objet avec une liste « questions ».")
    db = dict(raw)
    db.setdefault("course", "Mes QCM")
    chapters = dict(raw.get("chapters") or {})
    seen_ids = set()
    questions = []
    for i, q in enumerate(raw["questions"]):
        if not isinstance(q, dict) or not str(q.get("stem", "")).strip():
            raise ValueError(f"Question n°{i + 1} : énoncé manquant.")
        opts = q.get("options")
        if not isinstance(opts, list) or not opts:
            raise ValueError(f"Question n°{i + 1} : aucune proposition.")
        nq = dict(q)
        qid = str(q.get("id") or "").strip()
        if not qid or qid in seen_ids:
            qid = next_id(questions + [{"id": x} for x in seen_ids])
        seen_ids.add(qid)
        nq["id"] = qid
        nq["chapter"] = str(q.get("chapter") or "divers")
        chapters.setdefault(nq["chapter"], nq["chapter"])
        nq.setdefault("source", "")
        nq.setdefault("note", "")
        nq["is_annale"] = bool(q.get("is_annale", False))
        nq["options"] = []
        for o in opts:
            if not isinstance(o, dict):
                raise ValueError(f"Question n°{i + 1} : proposition invalide.")
            no = {**blank_option(), **o}
            no["correct"] = bool(no["correct"])
            no["doubtful"] = bool(no["doubtful"])
            nq["options"].append(no)
        questions.append(nq)
    db["chapters"] = chapters
    db["questions"] = questions
    return db


def merge_db(base: dict, incoming: dict) -> tuple[dict, int]:
    """Ajoute les questions de incoming absentes de base (même id = remplacée). Renvoie (db, nb ajoutées/maj)."""
    incoming = normalize_db(incoming)
    by_id = {q["id"]: i for i, q in enumerate(base["questions"])}
    questions = base["questions"][:]
    for q in incoming["questions"]:
        if q["id"] in by_id:
            questions[by_id[q["id"]]] = q
        else:
            questions.append(q)
    chapters = {**base["chapters"], **incoming["chapters"]}
    return {**base, "chapters": chapters, "questions": questions}, len(incoming["questions"])


def filter_questions(questions: list, chapters=None, annales_only: bool = False) -> list:
    return [q for q in questions
            if (not chapters or q["chapter"] in chapters)
            and (not annales_only or q.get("is_annale"))]


def shuffled_view(question: dict, rng: random.Random) -> list[int]:
    """Ordre d'affichage des propositions (indices d'origine)."""
    order = list(range(len(question["options"])))
    rng.shuffle(order)
    return order


def fmt_note(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")
