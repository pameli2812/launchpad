"""History tab - Analysis history and status management."""

import streamlit as st
from datetime import datetime

from utils.storage import (
    load_history,
    write_json
)

HISTORY_FILE = "data/history.json"


def save_history_to_disk():
    """
    Save session history locally.
    """

    serialized = []

    for entry in st.session_state.history:

        serialized.append({
            "jd_title": entry.jd_title,
            "company": entry.company,
            "goal_set_name": entry.goal_set_name,
            "overall_fit": entry.overall_fit,
            "verdict": entry.verdict,
            "status": entry.status,
            "analyzed_at":
            entry.analyzed_at.isoformat()
        })

    write_json(
        HISTORY_FILE,
        serialized
    )


def load_history_from_disk():
    """
    Load history from local JSON.
    """

    raw_history = load_history()

    loaded = []

    for item in raw_history:

        loaded.append(
            type(
                "HistoryEntry",
                (),
                {
                    "jd_title":
                    item.get(
                        "jd_title",
                        "Unknown"
                    ),

                    "company":
                    item.get(
                        "company",
                        "Unknown"
                    ),

                    "goal_set_name":
                    item.get(
                        "goal_set_name",
                        ""
                    ),

                    "overall_fit":
                    item.get(
                        "overall_fit",
                        0
                    ),

                    "verdict":
                    item.get(
                        "verdict",
                        "unknown"
                    ),

                    "status":
                    item.get(
                        "status",
                        "draft"
                    ),

                    "analyzed_at":
                    datetime.fromisoformat(
                        item.get(
                            "analyzed_at"
                        )
                    )
                    if item.get(
                        "analyzed_at"
                    )
                    else datetime.now()
                }
            )()
        )

    return loaded


def render_history_tab():
    """Render history tab."""

    # -------------------------
    # Load once on startup
    # -------------------------

    if (
        "history_loaded"
        not in st.session_state
    ):

        loaded_history = (
            load_history_from_disk()
        )

        if loaded_history:
            st.session_state.history = (
                loaded_history
            )

        st.session_state.history_loaded = (
            True
        )

    st.header("History")

    if not st.session_state.history:
        st.info("No analyses yet")
        return

    for i, entry in enumerate(
        st.session_state.history
    ):

        col1, col2, col3, col4 = (
            st.columns([3, 1, 1, 1])
        )

        with col1:

            st.write(
                f"**{entry.jd_title}** "
                f"@ {entry.company}"
            )

            time_str = ""
            if entry.analyzed_at:
                time_str = entry.analyzed_at.strftime('%m/%d %H:%M')
            
            st.caption(
                f"{entry.goal_set_name}"
                f" | "
                f"{time_str}"
            )

        with col2:

            st.metric(
                "Fit",
                f"{entry.overall_fit:.1f}"
            )

        with col3:

            icon = {
                "apply": "🟢",
                "borderline": "🟡",
                "skip": "🔴"
            }.get(
                entry.verdict,
                "❓"
            )

            st.write(
                f"{icon} "
                f"**{entry.verdict.title()}**"
            )

        with col4:

            statuses = [
                "draft",
                "pending",
                "applied",
                "skipped"
            ]

            current_index = (
                statuses.index(
                    entry.status
                )
                if entry.status
                in statuses
                else 0
            )

            new_status = st.selectbox(
                "Status",
                statuses,
                index=current_index,
                key=f"status_{i}"
            )

            if (
                new_status
                != entry.status
            ):

                st.session_state.history[
                    i
                ].status = new_status

                save_history_to_disk()

                st.success("✓")

        # ------------------
        # Delete row
        # ------------------

        if st.button(
            "🗑️ Delete",
            key=f"delete_{i}"
        ):

            del st.session_state.history[
                i
            ]

            save_history_to_disk()

            st.success(
                "Deleted"
            )

            st.rerun()

        st.divider()

    # -------------------------
    # Clear All History
    # -------------------------

    if st.button(
        "🧹 Clear History",
        use_container_width=True
    ):

        st.session_state.history = []

        save_history_to_disk()

        st.success(
            "History cleared"
        )

        st.rerun()