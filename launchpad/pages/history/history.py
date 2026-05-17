"""History tab - Analysis history and status management."""

import streamlit as st
from datetime import datetime
from utils.storage import load_history, write_json

HISTORY_FILE = "data/history.json"

VERDICT_COLORS = {
    "apply": ("#dcfce7", "#166534"),
    "borderline": ("#fef9c3", "#854d0e"),
    "skip": ("#fee2e2", "#991b1b"),
}


def save_history_to_disk():
    serialized = []
    for entry in st.session_state.history:
        serialized.append({
            "jd_title": entry.jd_title,
            "company": entry.company,
            "goal_set_name": entry.goal_set_name,
            "overall_fit": entry.overall_fit,
            "verdict": entry.verdict,
            "status": entry.status,
            "analyzed_at": entry.analyzed_at.isoformat(),
        })
    write_json(HISTORY_FILE, serialized)


def load_history_from_disk():
    raw_history = load_history()
    loaded = []
    for item in raw_history:
        loaded.append(
            type("HistoryEntry", (), {
                "jd_title": item.get("jd_title", "Unknown"),
                "company": item.get("company", "Unknown"),
                "goal_set_name": item.get("goal_set_name", ""),
                "overall_fit": item.get("overall_fit", 0),
                "verdict": item.get("verdict", "unknown"),
                "status": item.get("status", "draft"),
                "analyzed_at": datetime.fromisoformat(item["analyzed_at"]) if item.get("analyzed_at") else datetime.now(),
            })()
        )
    return loaded


def render_history_tab():

    if "history_loaded" not in st.session_state:
        loaded = load_history_from_disk()
        if loaded:
            st.session_state.history = loaded
        st.session_state.history_loaded = True

    st.header("History")

    if not st.session_state.history:
        st.info("No analyses yet. Run an analysis in the Analyze tab.")
        return

    # Summary stats
    total = len(st.session_state.history)
    applied = sum(1 for e in st.session_state.history if e.verdict == "apply")
    borderline = sum(1 for e in st.session_state.history if e.verdict == "borderline")
    skipped = sum(1 for e in st.session_state.history if e.verdict == "skip")

    s1, s2, s3, s4 = st.columns(4)
    with s1: st.metric("Total Analyses", total)
    with s2: st.metric("Strong Match", applied)
    with s3: st.metric("Borderline", borderline)
    with s4: st.metric("Skipped", skipped)

    st.divider()

    statuses = ["draft", "pending", "applied", "skipped"]

    for i, entry in enumerate(st.session_state.history):
        verdict_bg, verdict_tc = VERDICT_COLORS.get(entry.verdict, ("#f8f9fb", "#1a1a2e"))
        time_str = entry.analyzed_at.strftime("%d %b %Y, %H:%M") if entry.analyzed_at else "—"

        col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])

        with col1:
            st.markdown(f"**{entry.jd_title}** @ {entry.company}")
            st.caption(f"{entry.goal_set_name} · {time_str}")

        with col2:
            st.metric("Fit", f"{entry.overall_fit:.1f}")

        with col3:
            st.markdown(
                f"<div style='background:{verdict_bg}; color:{verdict_tc}; padding:4px 10px; "
                f"border-radius:12px; font-size:0.82rem; font-weight:600; text-align:center; margin-top:8px;'>"
                f"{entry.verdict.title()}</div>",
                unsafe_allow_html=True,
            )

        with col4:
            current_index = statuses.index(entry.status) if entry.status in statuses else 0
            new_status = st.selectbox("Status", statuses, index=current_index, key=f"status_{i}", label_visibility="collapsed")
            if new_status != entry.status:
                st.session_state.history[i].status = new_status
                save_history_to_disk()

        with col5:
            if st.button("Delete", key=f"delete_{i}"):
                del st.session_state.history[i]
                save_history_to_disk()
                st.rerun()

        st.divider()

    if st.button("Clear All History", use_container_width=True):
        st.session_state.history = []
        save_history_to_disk()
        st.rerun()