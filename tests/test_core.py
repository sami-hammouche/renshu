"""Tests de la logique pure. Lancer : python -m unittest discover -s tests"""
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from renshu import core  # noqa: E402
from renshu.store import Store  # noqa: E402

# Question type : 0 et 2 justes, 1 et 3 fausses, 4 douteuse.
Q = {"options": [{"correct": True}, {"correct": False}, {"correct": True},
                 {"correct": False}, {"correct": False, "doubtful": True}]}
AON = core.SCHEMES["tout-ou-rien"]
PEN = {"type": "penalty", "points": 1, "penalty": 0.25, "floor": 0}
PEN_NEG = {"type": "penalty", "points": 1, "penalty": 0.5, "floor": -1}
G = core.grade_question


class Correction(unittest.TestCase):
    def test_exact(self):
        r = G(Q, [0, 2])
        self.assertEqual(r["statuses"], ["hit", "neutral", "hit", "neutral", "doubtful"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["errors"], 0)

    def test_oubli(self):
        r = G(Q, [0])
        self.assertEqual(r["statuses"][2], "miss")
        self.assertFalse(r["ok"])
        self.assertEqual((r["errors"], r["misses"]), (1, 1))

    def test_coche_a_tort(self):
        r = G(Q, [0, 1, 2])
        self.assertEqual(r["statuses"][1], "wrong")
        self.assertFalse(r["ok"])
        self.assertEqual(r["wrongs"], 1)

    def test_douteuse_neutre(self):
        self.assertTrue(G(Q, [0, 2, 4])["ok"])
        self.assertTrue(G(Q, [0, 2])["ok"])

    def test_zero_bonne_reponse(self):
        z = {"options": [{"correct": False}, {"correct": False}]}
        self.assertTrue(G(z, [])["ok"])
        self.assertFalse(G(z, [1])["ok"])

    def test_rien_coche(self):
        r = G(Q, [])
        self.assertEqual(r["errors"], 2)
        self.assertEqual(r["statuses"], ["miss", "neutral", "miss", "neutral", "doubtful"])

    def test_tout_coche(self):
        r = G(Q, [0, 1, 2, 3, 4])
        self.assertEqual((r["errors"], r["hits"], r["wrongs"]), (2, 2, 2))


class Baremes(unittest.TestCase):
    def test_tout_ou_rien(self):
        self.assertEqual(core.score_question(G(Q, [0, 2]), AON), 1)
        self.assertEqual(core.score_question(G(Q, [0]), AON), 0)

    def test_penalite(self):
        self.assertEqual(core.score_question(G(Q, [0, 2]), PEN), 1)
        self.assertEqual(core.score_question(G(Q, [0]), PEN), 0.75)
        self.assertEqual(core.score_question(G(Q, [0, 1]), PEN), 0.5)

    def test_planchers(self):
        self.assertEqual(core.score_question(G(Q, [1, 3]), PEN), 0)
        self.assertEqual(core.score_question(G(Q, [1, 3]), PEN_NEG), -1)
        self.assertEqual(core.score_question(G(Q, [1]), PEN_NEG), -0.5)

    def test_note_sur_20(self):
        rs = [G(Q, [0, 2]), G(Q, [0]), G(Q, [0, 2]), G(Q, [])]
        s = core.score_quiz(rs, AON)
        self.assertEqual((s["total"], s["max"], s["ok_count"], s["on20"]), (2, 4, 2, 10))

    def test_note_negative_ramenee_a_zero(self):
        s = core.score_quiz([G(Q, [1, 3])], PEN_NEG)
        self.assertEqual((s["total"], s["on20"]), (-1, 0))

    def test_arrondi_comme_js(self):
        self.assertEqual(core.round2(0.125), 0.13)
        self.assertEqual(core.round2(2 / 3), 0.67)

    def test_format_note(self):
        self.assertEqual(core.fmt_note(13.5), "13,5")
        self.assertEqual(core.fmt_note(10.0), "10")


class Revision(unittest.TestCase):
    def test_monte_et_redescend(self):
        c = core.review(None, True, now=0)
        self.assertEqual((c["box"], c["seen"], c["streak"]), (2, 1, 1))
        c = core.review(c, True, now=0)
        self.assertEqual(c["box"], 3)
        self.assertEqual(c["due"], 3 * core.DAY)
        c = core.review(c, False, now=10)
        self.assertEqual((c["box"], c["wrong"], c["streak"], c["due"]), (1, 1, 0, 10))

    def test_plafond_boite_5(self):
        c = None
        for _ in range(10):
            c = core.review(c, True, now=0)
        self.assertEqual(c["box"], 5)

    def test_priorites(self):
        self.assertEqual(core.priority(None, 100), 2)
        self.assertEqual(core.priority({"seen": 1, "box": 1, "due": 50}, 100), 0)
        self.assertEqual(core.priority({"seen": 1, "box": 3, "due": 50}, 100), 1)
        self.assertEqual(core.priority({"seen": 1, "box": 3, "due": 500}, 100), 3)

    def test_pick_ratees_en_premier(self):
        pool = [{"id": f"q{i}"} for i in range(10)]
        stats = {"q3": {"seen": 2, "box": 1, "due": 0, "wrong": 1},
                 "q7": {"seen": 2, "box": 1, "due": 0, "wrong": 2}}
        for k in range(5):
            got = {q["id"] for q in core.pick(pool, stats, 2, now=100, rng=random.Random(k))}
            self.assertEqual(got, {"q3", "q7"})

    def test_pick_sans_doublon_et_limite(self):
        pool = [{"id": f"q{i}"} for i in range(5)]
        got = core.pick(pool, {}, 10, rng=random.Random(1))
        self.assertEqual(len(got), 5)
        self.assertEqual(len({q["id"] for q in got}), 5)

    def test_resume_et_chapitres(self):
        qs = [{"id": "a", "chapter": "05"}, {"id": "b", "chapter": "05"}, {"id": "c", "chapter": "06"}]
        stats = {"a": {"seen": 4, "wrong": 1, "box": 4, "due": 0},
                 "c": {"seen": 2, "wrong": 2, "box": 1, "due": 10 ** 12}}
        s = core.summary(qs, stats, now=100)
        self.assertEqual((s["seen"], s["mastered"], s["to_review"]), (2, 1, 1))
        ch = core.chapter_stats(qs, stats)
        self.assertAlmostEqual(ch["05"]["rate"], 0.75)
        self.assertEqual(ch["06"]["rate"], 0)
        self.assertEqual([q["id"] for q in core.weakest(qs, stats)], ["c", "a"])


class Donnees(unittest.TestCase):
    def test_html_autorise(self):
        self.assertEqual(core.safe_html("<code>ip a</code> & <script>x</script>"),
                         "<code>ip a</code> &amp; &lt;script&gt;x&lt;/script&gt;")
        self.assertEqual(core.safe_html("2<sup>32</sup><br/>"), "2<sup>32</sup><br>")
        self.assertEqual(core.safe_html("a <img src=x onerror=1>"), "a &lt;img src=x onerror=1&gt;")

    def test_normalise_complete_les_champs(self):
        db = core.normalize_db({"questions": [{"stem": "x", "options": [{"text": "a", "correct": 1}], "extra": 5}]})
        q = db["questions"][0]
        self.assertEqual(q["id"], "q001")
        self.assertEqual(q["chapter"], "divers")
        self.assertTrue(q["options"][0]["correct"] is True)
        self.assertEqual(q["extra"], 5)
        self.assertIn("divers", db["chapters"])

    def test_normalise_refuse_fichier_invalide(self):
        with self.assertRaises(ValueError):
            core.normalize_db({"foo": 1})
        with self.assertRaises(ValueError):
            core.normalize_db({"questions": [{"stem": "x", "options": []}]})

    def test_ids_dupliques(self):
        db = core.normalize_db({"questions": [{"id": "q001", "stem": "a", "options": [{"text": "x"}]},
                                              {"id": "q001", "stem": "b", "options": [{"text": "y"}]}]})
        self.assertEqual(len({q["id"] for q in db["questions"]}), 2)

    def test_fusion(self):
        base = core.normalize_db({"questions": [{"id": "q001", "stem": "a", "options": [{"text": "x"}]}]})
        db, n = core.merge_db(base, {"questions": [{"id": "q001", "stem": "A", "options": [{"text": "x"}]},
                                                    {"id": "q009", "stem": "b", "options": [{"text": "y"}]}]})
        self.assertEqual(n, 2)
        self.assertEqual([q["stem"] for q in db["questions"]], ["A", "b"])
        self.assertEqual(core.next_id(db["questions"]), "q010")

    def test_filtre(self):
        qs = [{"chapter": "05", "is_annale": True}, {"chapter": "05"}, {"chapter": "06", "is_annale": True}]
        self.assertEqual(len(core.filter_questions(qs, ["05"])), 2)
        self.assertEqual(len(core.filter_questions(qs, ["05"], annales_only=True)), 1)
        self.assertEqual(len(core.filter_questions(qs)), 3)

    def test_vraies_questions_valides(self):
        raw = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
        db = core.normalize_db(raw)
        self.assertEqual(len(db["questions"]), 54)
        for q in db["questions"]:
            self.assertIn(q["chapter"], db["chapters"])


class BilanParChapitre(unittest.TestCase):
    def test_tri_du_plus_faible(self):
        qs = [{"chapter": "05"}, {"chapter": "05"}, {"chapter": "06"}, {"chapter": "04"}]
        rs = [{"ok": True}, {"ok": False}, {"ok": True}, {"ok": False}]
        self.assertEqual(core.by_chapter(qs, rs), [("04", 0, 1), ("05", 1, 2), ("06", 1, 1)])


class Stockage(unittest.TestCase):
    def test_sauvegardes(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d))
            self.assertIsNotNone(s.daily_backup())
            self.assertIsNone(s.daily_backup())  # une seule par jour
            for _ in range(Store.KEEP_BACKUPS + 5):
                s.backup_questions("test")
            self.assertEqual(len(list((Path(d) / "sauvegardes").glob("questions_*.json"))), Store.KEEP_BACKUPS)

    def test_import_invalide_ne_touche_a_rien(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d))
            bad = Path(d) / "bad.json"
            bad.write_text('{"foo": 1}', encoding="utf-8")
            with self.assertRaises(ValueError):
                s.import_file(str(bad), replace=True)
            self.assertEqual(len(s.questions), 54)
            self.assertFalse((Path(d) / "sauvegardes").exists())

    def test_import_remplace_avec_sauvegarde(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d))
            new = Path(d) / "new.json"
            new.write_text(json.dumps({"questions": [{"stem": "x", "options": [{"text": "a"}]}]}), encoding="utf-8")
            self.assertEqual(s.import_file(str(new), replace=True), 1)
            self.assertEqual(len(Store(Path(d)).questions), 1)
            backups = list((Path(d) / "sauvegardes").glob("questions_*avant-import*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(len(json.loads(backups[0].read_text(encoding="utf-8"))["questions"]), 54)

    def test_cycle_complet(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d))
            self.assertEqual(len(s.questions), 54)
            qid = s.questions[0]["id"]
            s.record_answer(qid, False)
            r = [G(s.questions[0], [])]
            s.record_session("exam", r, ["04"], 65)
            s2 = Store(Path(d))
            self.assertEqual(s2.stats[qid]["wrong"], 1)
            self.assertEqual(s2.history[-1]["mode"], "exam")
            out = Path(d) / "export.json"
            s2.export_file(str(out))
            self.assertEqual(len(json.loads(out.read_text(encoding="utf-8"))["questions"]), 54)

    def test_progression_illisible_sauvegardee(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "progression.json").write_text("{pas du json", encoding="utf-8")
            s = Store(Path(d))
            self.assertEqual(s.stats, {})
            self.assertTrue(list(Path(d).glob("progression-illisible-*.json")))


if __name__ == "__main__":
    unittest.main()
