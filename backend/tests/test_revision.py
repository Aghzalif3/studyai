from studyai import db, revision


def test_schedule_progression():
    card = {"ease": 2.5, "interval_days": 0, "reps": 0}
    s1 = revision.schedule(card, 2, now=0)
    assert s1["interval_days"] == 1 and s1["reps"] == 1
    s2 = revision.schedule({**card, **s1}, 2, now=0)
    assert s2["interval_days"] == 6
    s3 = revision.schedule({**card, **s2}, 2, now=0)
    assert s3["interval_days"] == 15
    again = revision.schedule({**card, **s3}, 0, now=0)
    assert again["reps"] == 0 and again["lapses"] == 1 and again["due"] == 600


def test_stats_weak_notions():
    cid = db.create_course("c", "c.mp4", "/x", {})
    revision.record_attempt(cid, "qcm", 1, 3, 30, [
        {"question_id": "q1", "notion": "TVA", "correct": False},
        {"question_id": "q2", "notion": "TVA", "correct": False},
        {"question_id": "q3", "notion": "Bilan", "correct": True},
    ])
    st = revision.stats(cid)
    assert st["answers"] == 3
    assert st["weak_notions"][0]["notion"] == "TVA"
    assert all(w["notion"] != "Bilan" for w in st["weak_notions"])
