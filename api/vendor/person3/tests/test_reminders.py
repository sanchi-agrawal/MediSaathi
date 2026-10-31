import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
import reminders as rm
from schedule import build_schedule

START = date(2026, 10, 25)


def med(name="Dolo", pattern="1-0-1", days=5, form="tablet", **kw):
    r = {"name": name, "frequency_pattern": pattern, "duration_days": days, "form": form,
         "confirmed": True, "needs_review": False}
    r.update(kw)
    return r


def setup(meds=None, start=START):
    conn = rm.connect(":memory:")
    results = [build_schedule(m, start) for m in (meds or [med()])]
    return conn, results


def test_load_creates_one_row_per_dose():
    conn, results = setup()
    assert rm.load_schedule(conn, results) == 10
    row = conn.execute("SELECT * FROM dose_log ORDER BY due_at LIMIT 1").fetchone()
    assert row["medicine"] == "Dolo" and row["slot"] == "morning"
    assert row["due_at"] == "2026-10-25T08:00" and row["unit"] == "tablet" and row["amount"] == 1


def test_only_ok_results_create_doses():
    unconfirmed = med("Bad", confirmed=False)
    sos = med("Prn", "SOS", None)
    conn, results = setup([med(), unconfirmed, sos])
    assert rm.load_schedule(conn, results) == 10
    names = {r["medicine"] for r in conn.execute("SELECT medicine FROM dose_log")}
    assert names == {"Dolo"}


def test_reload_replaces_instead_of_duplicating():
    conn, results = setup()
    rm.load_schedule(conn, results)
    rm.load_schedule(conn, results)
    assert conn.execute("SELECT COUNT(*) FROM dose_log").fetchone()[0] == 10


def test_amounts_follow_the_schedule_half_tablets_and_syrup():
    conn, results = setup([med("Half", "0.5-0-0.5", 1),
                           med("Syr", "BD", 1, form="syrup", dose_quantity=5, dose_unit="ml")])
    rm.load_schedule(conn, results)
    rows = {(r["medicine"], r["slot"]): (r["amount"], r["unit"])
            for r in conn.execute("SELECT * FROM dose_log")}
    assert rows[("Half", "morning")] == (0.5, "tablet")
    assert rows[("Syr", "night")] == (5, "ml")


def test_custom_slot_times():
    conn, results = setup([med(pattern="1-0-0", days=1)])
    rm.load_schedule(conn, results, {**rm.DEFAULT_SLOT_TIMES, "morning": time(9, 30)})
    assert conn.execute("SELECT due_at FROM dose_log").fetchone()[0] == "2026-10-25T09:30"


def test_bad_slot_times_rejected():
    conn, results = setup()
    with pytest.raises(ValueError):
        rm.load_schedule(conn, results, {"morning": time(8, 0)})


def test_todays_doses():
    conn, results = setup()
    rm.load_schedule(conn, results)
    assert [d["slot"] for d in rm.todays_doses(conn, START)] == ["morning", "night"]
    assert rm.todays_doses(conn, date(2026, 11, 30)) == []


def test_mark_taken_once():
    conn, results = setup()
    rm.load_schedule(conn, results)
    dose = rm.todays_doses(conn, START)[0]
    now = datetime(2026, 10, 25, 8, 5)
    assert rm.mark_taken(conn, dose["id"], now) is True
    assert rm.mark_taken(conn, dose["id"], now) is False
    assert rm.mark_taken(conn, 9999, now) is False
    d = rm.todays_doses(conn, START)[0]
    assert d["status"] == "taken" and d["taken_at"] == "2026-10-25T08:05"


def test_not_overdue_within_grace_period():
    conn, results = setup()
    rm.load_schedule(conn, results)
    assert rm.overdue_doses(conn, datetime(2026, 10, 25, 8, 59)) == []


def test_overdue_after_60_minutes():
    conn, results = setup()
    rm.load_schedule(conn, results)
    od = rm.overdue_doses(conn, datetime(2026, 10, 25, 9, 0))
    assert [d["slot"] for d in od] == ["morning"]


def test_taken_dose_is_never_overdue():
    conn, results = setup()
    rm.load_schedule(conn, results)
    rm.mark_taken(conn, rm.todays_doses(conn, START)[0]["id"], datetime(2026, 10, 25, 8, 1))
    assert rm.overdue_doses(conn, datetime(2026, 10, 25, 12, 0)) == []


def test_old_doses_are_not_alerted():
    conn, results = setup()
    rm.load_schedule(conn, results)
    od = rm.overdue_doses(conn, datetime(2026, 10, 27, 12, 0))
    assert all(d["due_at"] >= "2026-10-26T12:00" for d in od)


def test_send_missed_alerts_once():
    conn, results = setup()
    rm.load_schedule(conn, results)
    sent = []
    now = datetime(2026, 10, 25, 9, 30)
    assert len(rm.send_missed_alerts(conn, now, lambda m: sent.append(m) or True)) == 1
    assert rm.send_missed_alerts(conn, now, lambda m: sent.append(m) or True) == []
    assert len(sent) == 1


def test_failed_send_is_retried():
    conn, results = setup()
    rm.load_schedule(conn, results)
    now = datetime(2026, 10, 25, 9, 30)
    assert rm.send_missed_alerts(conn, now, lambda m: False) == []
    assert len(rm.send_missed_alerts(conn, now, lambda m: True)) == 1


def test_message_content():
    dose = {"medicine": "Dolo 650", "slot": "morning", "amount": 1, "unit": "tablet",
            "due_at": "2026-10-25T08:00"}
    msg = rm.build_missed_message(dose)
    assert "Dolo 650" in msg and "1 tablet" in msg and "08:00 AM" in msg
    assert "not medical advice" in msg and "DEMO" not in msg
    assert "DEMO" in rm.build_missed_message(dose, demo=True)


def test_simulate_sends_labelled_message_and_keeps_log_unchanged():
    conn, results = setup()
    rm.load_schedule(conn, results)
    sent = []
    msg, ok = rm.simulate_missed_dose(conn, lambda m: sent.append(m) or True)
    assert ok and "DEMO" in sent[0] and msg == sent[0]
    assert conn.execute("SELECT COUNT(*) FROM dose_log WHERE alerted=1 OR status!='pending'"
                        ).fetchone()[0] == 0


def test_simulate_with_no_doses_or_no_sender():
    conn = rm.connect(":memory:")
    assert rm.simulate_missed_dose(conn, lambda m: True) == (None, False)
    conn2, results = setup()
    rm.load_schedule(conn2, results)
    msg, ok = rm.simulate_missed_dose(conn2, None)
    assert msg and ok is False


def test_telegram_sender_builds_request_and_hides_failures():
    calls = []
    send = rm.make_sender("TOKEN123", "42", post=lambda url, data: calls.append((url, data)) or True)
    assert send("hello") is True
    assert calls[0][0] == "https://api.telegram.org/botTOKEN123/sendMessage"
    assert calls[0][1] == {"chat_id": "42", "text": "hello"}

    def boom(url, data):
        raise RuntimeError("network down TOKEN123")
    assert rm.make_sender("TOKEN123", "42", post=boom)("x") is False


def test_sender_from_env_needs_real_values():
    assert rm.sender_from_env({}) is None
    assert rm.sender_from_env({"TELEGRAM_BOT_TOKEN": "your_bot_token_here",
                               "TELEGRAM_CHAT_ID": "caregiver_chat_id_here"}) is None
    assert rm.sender_from_env({"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "99"}) is not None


# ---------- refill alerts ----------

def alerts_for(days, today, pattern="1-0-0"):
    results = [build_schedule(med(pattern=pattern, days=days), START)]
    return rm.refill_alerts(results, today)


def test_refill_alert_for_long_course():
    # 30 days from 25 Oct ends 23 Nov, refill date 20 Nov
    assert alerts_for(30, date(2026, 11, 19)) == []
    a = alerts_for(30, date(2026, 11, 20))
    assert a[0]["level"] == "warning" and "refill" in a[0]["message"]


def test_course_ending_soon_and_finished():
    assert "ends in 2 days" in alerts_for(5, date(2026, 10, 28))[0]["message"]
    assert "ends in 1 day " in alerts_for(5, date(2026, 10, 29))[0]["message"]
    assert "finished" in alerts_for(5, date(2026, 10, 30))[0]["message"]
    assert alerts_for(5, date(2026, 10, 26)) == []


def test_no_alerts_for_unscheduled_medicines():
    results = [build_schedule(med(confirmed=False), START)]
    assert rm.refill_alerts(results, date(2026, 10, 30)) == []
