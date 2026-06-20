"""Applications, scores, signals and the append-only state history."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from app import util


def get_or_create_application(conn: sqlite3.Connection, candidate_id: int, job_id: int,
                              profile_version_id: Optional[int]) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM application WHERE candidate_id=? AND job_id=?",
                       (candidate_id, job_id)).fetchone()
    if row:
        return dict(row)
    ts = util.now_iso()
    cur = conn.execute(
        "INSERT INTO application (candidate_id, job_id, current_state, profile_version_id, "
        "created_at) VALUES (?,?,?,?,?)",
        (candidate_id, job_id, "DISCOVERED", profile_version_id, ts))
    app_id = cur.lastrowid
    _add_history(conn, app_id, None, "DISCOVERED", "discovered")
    return dict(conn.execute("SELECT * FROM application WHERE id=?", (app_id,)).fetchone())


def transition(conn: sqlite3.Connection, application_id: int, to_state: str,
               reason: Optional[str] = None, actor: str = "SYSTEM") -> None:
    cur = conn.execute("SELECT current_state FROM application WHERE id=?",
                       (application_id,)).fetchone()
    from_state = cur["current_state"] if cur else None
    conn.execute(
        "UPDATE application SET current_state=?, reason_code=?, updated_at=? WHERE id=?",
        (to_state, reason, util.now_iso(), application_id))
    _add_history(conn, application_id, from_state, to_state, reason, actor)


def _add_history(conn: sqlite3.Connection, application_id: int, from_state: Optional[str],
                 to_state: str, reason: Optional[str], actor: str = "SYSTEM") -> None:
    conn.execute(
        "INSERT INTO application_state_history (application_id, from_state, to_state, "
        "actor_type, reason, created_at) VALUES (?,?,?,?,?,?)",
        (application_id, from_state, to_state, actor, reason, util.now_iso()))


def write_score(conn: sqlite3.Connection, application_id: int, result: Dict[str, Any],
                signals: List[Dict[str, Any]]) -> int:
    """Persist a new current score (retiring the previous one) + its signals."""
    conn.execute("UPDATE application_score SET is_current=0 "
                 "WHERE application_id=? AND is_current=1", (application_id,))
    cur = conn.execute(
        "INSERT INTO application_score (application_id, trajectory_direction, trajectory_score, "
        "skill_score, location_score, experience_score, salary_fit_score, career_alignment_score, "
        "total_score, confidence, signal_density, leap_override, scoring_model_version, "
        "breakdown_json, explanation_summary, is_current, scored_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
        (application_id, result.get("trajectory_direction"), result.get("trajectory_score"),
         result.get("skill_score"), result.get("location_score"), result.get("experience_score"),
         result.get("salary_fit_score"), result.get("trajectory_score"),
         result["total_score"], result.get("confidence"), result.get("signal_density"),
         1 if result.get("leap_override") else 0, result["scoring_model_version"],
         util.dumps(result.get("breakdown", {})), result.get("explanation_summary"),
         util.now_iso()))
    score_id = cur.lastrowid
    for s in signals:
        conn.execute(
            "INSERT INTO score_signal (score_id, signal_type, direction, weight, label, detail) "
            "VALUES (?,?,?,?,?,?)",
            (score_id, s["signal_type"], s["direction"], s.get("weight"),
             s["label"], s.get("detail")))
    conn.execute("UPDATE application SET priority_score=? WHERE id=?",
                 (result["total_score"], application_id))
    return score_id  # type: ignore[return-value]


def _feed_where(candidate_id: int, states: Optional[List[str]],
                search: Optional[str]) -> Any:
    clause = " WHERE a.candidate_id=? AND a.deleted_at IS NULL"
    params: List[Any] = [candidate_id]
    if states:
        clause += " AND a.current_state IN (%s)" % ",".join("?" for _ in states)
        params += states
    if search:
        clause += " AND (j.title LIKE ? OR c.name LIKE ?)"
        like = f"%{search}%"
        params += [like, like]
    return clause, params


def ranked_applications(conn: sqlite3.Connection, candidate_id: int,
                        states: Optional[List[str]] = None,
                        search: Optional[str] = None,
                        limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Ranked feed: applications + job + current score, paginated."""
    where, params = _feed_where(candidate_id, states, search)
    q = (
        "SELECT a.id AS application_id, a.current_state, a.reason_code, a.priority_score, "
        "a.verdict, j.title, j.location, j.is_remote, j.source, j.source_url, c.name AS company, "
        "s.trajectory_direction, s.total_score, s.confidence, s.leap_override, "
        "s.signal_density, s.explanation_summary "
        "FROM application a "
        "JOIN job j ON j.id=a.job_id "
        "JOIN company c ON c.id=j.company_id "
        "LEFT JOIN application_score s ON s.application_id=a.id AND s.is_current=1"
        + where
        + " ORDER BY a.priority_score DESC NULLS LAST, a.id DESC LIMIT ? OFFSET ?"
    )
    rows = conn.execute(q, params + [limit, offset]).fetchall()
    return [dict(r) for r in rows]


def count_applications(conn: sqlite3.Connection, candidate_id: int,
                       states: Optional[List[str]] = None,
                       search: Optional[str] = None) -> int:
    where, params = _feed_where(candidate_id, states, search)
    q = ("SELECT COUNT(*) FROM application a JOIN job j ON j.id=a.job_id "
         "JOIN company c ON c.id=j.company_id" + where)
    return int(conn.execute(q, params).fetchone()[0])


# Verdict -> (state, reason). BOOKMARK intentionally absent (no transition).
_VERDICT_TRANSITION = {
    "INTERESTED": ("AWAITING_REVIEW", None),
    "NOT_INTERESTED": ("REJECTED", "USER_DECLINED"),
    "WRONG_MATCH": ("REJECTED", "WRONG_MATCH"),
}


def set_verdict(conn: sqlite3.Connection, candidate_id: int, application_id: int,
                verdict: str, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Persist a human triage verdict (+note) and drive the state machine.
    Returns None if the application is not owned by this candidate."""
    row = conn.execute(
        "SELECT current_state FROM application WHERE id=? AND candidate_id=? AND deleted_at IS NULL",
        (application_id, candidate_id)).fetchone()
    if not row:
        return None
    conn.execute("UPDATE application SET verdict=?, verdict_note=?, verdict_at=? WHERE id=?",
                 (verdict, note, util.now_iso(), application_id))
    current = row["current_state"]
    if verdict in _VERDICT_TRANSITION:
        to_state, reason = _VERDICT_TRANSITION[verdict]
        transition(conn, application_id, to_state, reason or f"verdict:{verdict}", actor="CANDIDATE")
        current = to_state
    return {"application_id": application_id, "verdict": verdict,
            "verdict_note": note, "current_state": current}


def summary_counts(conn: sqlite3.Connection, candidate_id: int) -> Dict[str, Any]:
    by_state = {r["current_state"]: r["n"] for r in conn.execute(
        "SELECT current_state, COUNT(*) AS n FROM application "
        "WHERE candidate_id=? AND deleted_at IS NULL GROUP BY current_state", (candidate_id,))}
    leaps = conn.execute(
        "SELECT COUNT(*) FROM application a JOIN application_score s "
        "ON s.application_id=a.id AND s.is_current=1 "
        "WHERE a.candidate_id=? AND s.leap_override=1 AND a.deleted_at IS NULL",
        (candidate_id,)).fetchone()[0]
    verdicts = {r["verdict"]: r["n"] for r in conn.execute(
        "SELECT verdict, COUNT(*) AS n FROM application WHERE candidate_id=? "
        "AND verdict IS NOT NULL AND deleted_at IS NULL GROUP BY verdict", (candidate_id,))}
    last_job = conn.execute("SELECT MAX(discovered_at) FROM job").fetchone()[0]
    last_run = conn.execute("SELECT MAX(finished_at) FROM discovery_run").fetchone()[0]
    last_discovery = max([x for x in (last_job, last_run) if x], default=None)
    return {
        "by_state": by_state, "leaps": leaps,
        "interested": verdicts.get("INTERESTED", 0),
        "not_interested": verdicts.get("NOT_INTERESTED", 0),
        "bookmarked": verdicts.get("BOOKMARK", 0),
        "wrong_match": verdicts.get("WRONG_MATCH", 0),
        "last_discovery_at": last_discovery,
    }


def get_application_for_candidate(conn: sqlite3.Connection, candidate_id: int,
                                  application_id: int) -> Optional[Dict[str, Any]]:
    """Ownership-scoped single application + job + current score (or None)."""
    row = conn.execute(
        "SELECT a.id AS application_id, a.current_state, a.reason_code, a.priority_score, "
        "a.verdict, a.verdict_note, "
        "j.title, j.description_text, j.location, j.is_remote, j.source, j.source_url, "
        "c.name AS company, s.trajectory_direction, s.total_score, s.confidence, "
        "s.leap_override, s.signal_density, s.explanation_summary, s.scoring_model_version "
        "FROM application a JOIN job j ON j.id=a.job_id JOIN company c ON c.id=j.company_id "
        "LEFT JOIN application_score s ON s.application_id=a.id AND s.is_current=1 "
        "WHERE a.id=? AND a.candidate_id=? AND a.deleted_at IS NULL",
        (application_id, candidate_id)).fetchone()
    return dict(row) if row else None


def get_signals(conn: sqlite3.Connection, application_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT ss.signal_type, ss.direction, ss.label, ss.detail "
        "FROM score_signal ss "
        "JOIN application_score s ON s.id=ss.score_id AND s.is_current=1 "
        "WHERE s.application_id=?", (application_id,)).fetchall()
    return [dict(r) for r in rows]
