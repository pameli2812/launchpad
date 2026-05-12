"""History tab - Analysis history and status management."""

import streamlit as st


def render_history_tab():
    """Render the History tab content."""
    st.header("History")
    if not st.session_state.history:
        st.info("No analyses yet")
    else:
        for i, entry in enumerate(st.session_state.history):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**{entry.jd_title}** @ {entry.company}")
                st.caption(f"{entry.goal_set_name} | {entry.analyzed_at.strftime('%m/%d %H:%M')}")
            
            with col2:
                st.metric("Fit", f"{entry.overall_fit:.1f}")
            
            with col3:
                icon = {"apply": "🟢", "borderline": "🟡", "skip": "🔴"}.get(entry.verdict, "❓")
                new_status = st.selectbox(
                    "Status",
                    ["draft", "pending", "applied", "skipped"],
                    index=["draft", "pending", "applied", "skipped"].index(entry.status),
                    key=f"status_{i}"
                )
                if new_status != entry.status:
                    st.session_state.history[i].status = new_status
                    st.success("✓")
            
            st.divider()
