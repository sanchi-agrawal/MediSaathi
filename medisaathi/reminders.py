"""Dose log, missed-dose alerts and refill alerts (Person 3).

Rules:
  * Doses come ONLY from schedule results with status 'ok' (confirmed, explicit quantities).
  * Reminder clock times are the user's own settings, not medical instructions.
  * Messages only report what the prescription said and whether a dose was marked.
    They never advise on doses.
"""
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta

DB_PATH = "medisaathi.db"
SLOTS = ["morning", "noon", "night", "bedtime"]
DEFAULT_SLOT_TIMES = {"morning": time(8, 0), "noon": time(13, 0),
                      "night": time(20, 0), "bedtime": time(22, 0)}
GRACE_MINUTES = 60          # alert the caregiver this long after a dose is due
LOOKBACK_HOURS = 24         # never alert for doses older than this (avoids spam)
REFILL_WARN_DAYS = 2

FOOTER = "Reminder and information tool, not medical advice."

SCHEMA = """
CREATE TABLE IF NOT EXISTS dose_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine TEXT NOT NULL,
    slot TEXT NOT NULL,
    amount REAL NOT NULL,
    unit TEXT NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    taken_at TEXT,
    alerted INTEGER NOT NULL DEFAULT 0,
    UNIQUE (medicine, slot, due_at)
)"""


# ---------- database ----------

def connect(path=DB_PATH):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def _check_slot_times(slot_times):
    if set(slot_times) != set(SLOTS) or not all(isinstance(t, time) for t in slot_times.values()):
        raise ValueError("slot_times needs a datetime.time for morning, noon, night and bedtime")


def load_schedule(conn, results, slot_times=None):
    """Replace the dose log with doses from schedule results (status 'ok' only).

    Replaces everything, so confirming a changed prescription never leaves old doses behind.
    Returns the number of doses created.
    """
    slot_times = slot_times or DEFAULT_SLOT_TIMES
    _check_slot_times(slot_times)
    conn.execute("DELETE FROM dose_log")
    count = 0
    for r in results:
        if r.get("status") != "ok":
            continue
        for day in range(r["duration_days"]):
            d = r["start_date"] + timedelta(days=day)
            for slot in SLOTS:
                amount = r["doses_by_slot"][slot]
                if amount and amount > 0:
                    due = datetime.combine(d, slot_times[slot]).isoformat(timespec="minutes")
                    conn.execute(
                        "INSERT OR IGNORE INTO dose_log (medicine, slot, amount, unit, due_at) "
                        "VALUES (?, ?, ?, ?, ?)", (r["name"], slot, amount, r["unit"], due))
                    count += 1
    conn.commit()
    return count


def todays_doses(conn, today):
    rows = conn.execute("SELECT * FROM dose_log WHERE due_at LIKE ? ORDER BY due_at, medicine",
                        (today.isoformat() + "%",)).fetchall()
    return [dict(r) for r in rows]


def mark_taken(conn, dose_id, now):
    """True if a pending dose was marked taken. Marking twice or an unknown id is harmless."""
    cur = conn.execute("UPDATE dose_log SET status='taken', taken_at=? "
                       "WHERE id=? AND status='pending'",
                       (now.isoformat(timespec="minutes"), dose_id))
    conn.commit()
    return cur.rowcount == 1


# ---------- missed doses ----------

def overdue_doses(conn, now, grace_minutes=GRACE_MINUTES, lookback_hours=LOOKBACK_HOURS):
    """Pending, not-yet-alerted doses more than grace_minutes late (but not ancient)."""
    latest_due = (now - timedelta(minutes=grace_minutes)).isoformat(timespec="minutes")
    earliest_due = (now - timedelta(hours=lookback_hours)).isoformat(timespec="minutes")
    rows = conn.execute(
        "SELECT * FROM dose_log WHERE status='pending' AND alerted=0 "
        "AND due_at <= ? AND due_at >= ? ORDER BY due_at", (latest_due, earliest_due)).fetchall()
    return [dict(r) for r in rows]


def _fmt_amount(a):
    return str(int(a)) if float(a).is_integer() else str(a)


def build_missed_message(dose, demo=False):
    due = datetime.fromisoformat(dose["due_at"])
    text = (f"MediSaathi: the {dose['slot']} dose of {dose['medicine']} "
            f"({_fmt_amount(dose['amount'])} {dose['unit']}, due {due.strftime('%d %b, %I:%M %p')}) "
            f"has not been marked as taken.")
    if demo:
        text = "[DEMO - simulated missed dose] " + text
    return text + "\n" + FOOTER


def send_missed_alerts(conn, now, sender):
    """Send one message per overdue dose. A failed send leaves the dose to retry next time.
    Returns the list of messages that were sent."""
    sent = []
    for dose in overdue_doses(conn, now):
        msg = build_missed_message(dose)
        if sender(msg):
            conn.execute("UPDATE dose_log SET alerted=1 WHERE id=?", (dose["id"],))
            sent.append(msg)
    conn.commit()
    return sent


def simulate_missed_dose(conn, sender):
    """Demo button: send a clearly labelled alert for the next pending dose.
    Does not change the dose log. Returns (message, sent_ok); message is None if no doses."""
    row = conn.execute("SELECT * FROM dose_log WHERE status='pending' "
                       "ORDER BY due_at LIMIT 1").fetchone()
    if row is None:
        return None, False
    msg = build_missed_message(dict(row), demo=True)
    return msg, bool(sender(msg)) if sender else False


# ---------- Telegram ----------

def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=10) as resp:
        return 200 <= resp.status < 300


def make_sender(token, chat_id, post=_post):
    """Returns send(text) -> bool. Never raises and never prints the token."""
    def send(text):
        try:
            return bool(post(f"https://api.telegram.org/bot{token}/sendMessage",
                             {"chat_id": chat_id, "text": text}))
        except Exception:
            return False
    return send


def sender_from_env(env=None, post=_post):
    env = os.environ if env is None else env
    token, chat_id = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id or token.startswith("your_") or chat_id.startswith("caregiver_"):
        return None
    return make_sender(token, chat_id, post)


# ---------- refill / run-out alerts ----------

def refill_alerts(results, today):
    """Date-based alerts from schedule results (status 'ok' only). No dose advice."""
    alerts = []
    for r in results:
        if r.get("status") != "ok":
            continue
        end, refill = r["end_date"], r["refill_date"]
        days_left = (end - today).days + 1
        if today > end:
            alerts.append({"name": r["name"], "level": "info",
                           "message": f"{r['name']}: course finished on {end.strftime('%d %b %Y')}."})
        elif refill and today >= refill:
            alerts.append({"name": r["name"], "level": "warning",
                           "message": f"{r['name']}: runs out on {end.strftime('%d %b %Y')}. "
                                      f"Time to order a refill."})
        elif days_left <= REFILL_WARN_DAYS:
            word = "day" if days_left == 1 else "days"
            alerts.append({"name": r["name"], "level": "info",
                           "message": f"{r['name']}: course ends in {days_left} {word} "
                                      f"({end.strftime('%d %b %Y')})."})
    return alerts
