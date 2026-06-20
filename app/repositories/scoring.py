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


def ranked_applications(conn: sqlite3.Connection, candidate_id: int,
                        states: Optional[List[str]] = None,
                        search: Optional[str] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
    """Ranked feed for the (future) dashboard: applications + job + current score."""
    q = (
        "SELECT a.id AS application_id, a.current_state, a.reason_code, a.priority_score, "
        "j.title, j.location, j.is_remote, j.source, j.source_url, c.name AS company, "
        "s.trajectory_direction, s.total_score, s.confidence, s.leap_override, "
        "s.explanation_summary "
        "FROM application a "
        "JOIN job j ON j.id=a.job_id "
        "JOIN company c ON c.id=j.company_id "
        "LEFT JOIN application_score s ON s.application_id=a.id AND s.is_current=1 "
        "WHERE a.candidate_id=? AND a.deleted_at IS NULL"
    )
    params: List[Any] = [candidate_id]
    if states:
        q += " AND a.current_state IN (%s)" % ",".join("?" for _ in states)
        params += states
    if search:
        q += " AND (j.title LIKE ? OR c.name LIKE ?)"
        like = f"%{search}%"
        params += [like, like]
    q += " ORDER BY a.priority_score DESC NULLS LAST, a.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def get_application_for_candidate(conn: sqlite3.Connection, candidate_id: int,
                                  application_id: int) -> Optional[Dict[str, Any]]:
    """Ownership-scoped single application + job + current score (or None)."""
    row = conn.execute(
        "SELECT a.id AS application_id, a.current_state, a.reason_code, a.priority_score, "
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
