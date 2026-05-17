"""Analyse tab - JD analysis and resume scoring."""

import streamlit as st
import uuid
import hashlib
from datetime import datetime

from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.models import HistoryEntry
from utils.storage import write_json


HISTORY_FILE = "data/history.json"


def get_resume_hash(text: str) -> str:
    return hashlib.sha256(
        text.encode()
    ).hexdigest()[:12]


def get_active_goal_set():

    if not st.session_state.active_goal_set_id:
        return None

    return st.session_state.goal_sets.get(
        st.session_state.active_goal_set_id
    )


def render_verdict_banner(
    verdict: str
):

    if verdict == "apply":

        st.success(
            "✅ **RECOMMENDED — "
            "Strong match. "
            "Apply with your current resume.**"
        )

    elif verdict == "borderline":

        st.warning(
            "⚠️ **BORDERLINE — "
            "Possible match. "
            "Address gaps before applying.**"
        )

    else:

        st.error(
            "🚫 **NOT RECOMMENDED — "
            "Weak match. "
            "Significant gaps exist.**"
        )

        if st.button(
            "Proceed anyway — "
            "get best-case resume changes",
            key="override_btn"
        ):
            st.session_state.force_suggestions = True

def render_scorecard_table(scores):
    """
    Render readable scorecard table
    without raw HTML showing.
    """

    score_data = []

    for s in sorted(
        scores,
        key=lambda x: x.score,
        reverse=True
    ):

        if s.score >= 8:
            emoji = "🟢"

        elif s.score >= 6:
            emoji = "🟡"

        else:
            emoji = "🔴"

        score_data.append({
            "Metric":
            s.dimension,

            "Score":
            f"{emoji} {s.score:.1f}/10",

            "Comment":
            s.remark
        })

    st.dataframe(
        score_data,
        use_container_width=True,
        hide_index=True
    )

    # Inject CSS to fix white header
    st.markdown(
        """
        <style>
        div[data-testid="stDataFrame"] thead tr th {
            background-color: #1e293b !important;
            color: white !important;
            font-weight: bold !important;
        }

        div[data-testid="stDataFrame"] tbody tr td {
            color: inherit !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
def render_scorecard_table1(
    scores
):
    """
    Improved readable scorecard.
    """

    sorted_scores = sorted(
        scores,
        key=lambda s: s.score,
        reverse=True
    )

    rows = ""

    for s in sorted_scores:

        val = f"{s.score:.1f}"

        if s.score >= 8:
            score_color = "#15803d"

        elif s.score >= 6:
            score_color = "#b45309"

        else:
            score_color = "#dc2626"

        rows += f"""
        <tr style='border-bottom:1px solid #ddd;'>
            <td style='padding:12px;
                       color:#111827;
                       font-weight:600;'>
                {s.dimension}
            </td>

            <td style='padding:12px;
                       text-align:center;
                       color:{score_color};
                       font-weight:bold;'>
                {val}
            </td>

            <td style='padding:12px;
                       color:#374151;'>
                {s.remark}
            </td>
        </tr>
        """

    st.markdown(
        f"""
        <table style='
            width:100%;
            border-collapse:collapse;
            border:1px solid #ddd;
            border-radius:10px;
            overflow:hidden;
        '>

            <thead>
                <tr style='
                    background:#1e293b;
                '>

                    <th style='
                        padding:14px;
                        color:white;
                        text-align:left;
                    '>
                        Metric
                    </th>

                    <th style='
                        padding:14px;
                        color:white;
                        text-align:center;
                    '>
                        Score
                    </th>

                    <th style='
                        padding:14px;
                        color:white;
                        text-align:left;
                    '>
                        Comment
                    </th>

                </tr>
            </thead>

            <tbody>
                {rows}
            </tbody>

        </table>
        """,
        unsafe_allow_html=True
    )


def save_history_locally():
    """
    Save history JSON.
    """

    serialized = []

    for entry in st.session_state.history:

        serialized.append({
            "jd_title": entry.jd_title,
            "company": entry.company,
            "goal_set_name":
            entry.goal_set_name,

            "overall_fit":
            entry.overall_fit,

            "verdict":
            entry.verdict,

            "status":
            entry.status,

            "analyzed_at":
            entry.analyzed_at.isoformat()
        })

    write_json(
        HISTORY_FILE,
        serialized
    )


def render_analyse_tab():

    if not st.session_state.resume_text:
        st.warning(
            "Upload resume in Setup first"
        )
        return

    active_gs = get_active_goal_set()

    if not active_gs:
        st.warning(
            "Create a goal set first"
        )
        return

    st.header("Analyze JD")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.write(
            f"**Active:** "
            f"{active_gs.name}"
        )

    with col2:
        goals_str = ", ".join(
            [
                g.label
                for g in active_gs.goals[:3]
            ]
        )

        st.caption(
            f"Goals: {goals_str}"
        )

    st.divider()

    jd_text = st.text_area(
        "Paste Job Description",
        height=300
    )

    jd_url = st.text_input(
        "URL (optional)"
    )

    col1, col2 = st.columns(2)

    with col1:

        analyze_btn = st.button(
            "🔍 Analyze",
            use_container_width=True
        )

    with col2:

        if st.button(
            "Clear",
            use_container_width=True
        ):
            st.session_state.current_analysis = None
            st.session_state.pop(
                "suggestions",
                None
            )
            st.rerun()

    # ---------------------------------
    # ANALYZE
    # ---------------------------------

    if analyze_btn and jd_text:

        with st.spinner(
            "Analyzing..."
        ):

            try:

                jd_json = extract_jd(
                    jd_text,
                    jd_url
                )

                scorecard = (
                    analyze_scorecard(
                        st.session_state.resume_text,
                        jd_json,
                        [
                            {
                                "id": g.id,
                                "label": g.label,
                                "description":
                                g.description,
                                "confidence":
                                g.confidence
                            }
                            for g in active_gs.goals
                        ]
                    )
                )

                st.session_state.current_analysis = {
                    "jd": jd_json,
                    "scorecard":
                    scorecard,
                    "resume_original":
                    st.session_state.resume_text,
                    "resume_hash":
                    get_resume_hash(
                        st.session_state.resume_text
                    )
                }

                st.success(
                    "✓ Analysis done!"
                )

                st.rerun()

            except Exception as e:
                st.error(str(e))

    # ---------------------------------
    # RESULTS
    # ---------------------------------

    if st.session_state.current_analysis:

        analysis = (
            st.session_state
            .current_analysis
        )

        scorecard = (
            analysis["scorecard"]
        )

        jd = analysis["jd"]

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Overall Fit",
                f"{scorecard.overall_fit:.1f}/10"
            )

        with col2:
            st.metric(
                "Role",
                jd.get(
                    "title",
                    "?"
                )[:40]
            )

        render_verdict_banner(
            scorecard.verdict
        )

        st.divider()

        st.subheader("Summary")

        st.info(
            scorecard.summary
        )

        st.divider()

        st.subheader(
            "Scorecard"
        )

        render_scorecard_table(
            scorecard.scores
        )

        if scorecard.gaps:

            st.divider()

            st.subheader(
                "Gaps to address"
            )

            for gap in scorecard.gaps:
                st.write(
                    f"• {gap}"
                )

        st.divider()

        show_suggestions = (
            scorecard.verdict
            in (
                "apply",
                "borderline"
            )
            or st.session_state.get(
                "force_suggestions",
                False
            )
        )

        col1, col2, col3 = (
            st.columns(3)
        )

        # -----------------------
        # Suggestions
        # -----------------------

        with col1:

            if (
                show_suggestions
                and st.button(
                    "💡 Get Suggestions",
                    use_container_width=True
                )
            ):

                with st.spinner(
                    "Generating..."
                ):

                    # sugg = (
                    #     generate_resume_suggestions(
                    #         st.session_state.resume_text,
                    #         jd,
                    #         scorecard.gaps,
                    #         override=(
                    #             scorecard.verdict
                    #             == "skip"
                    #         )
                    #     )
                    # )

                    # st.session_state.suggestions = (
                    #     sugg
                    # )
                    try:

                        sugg = (
                            generate_resume_suggestions(
                                st.session_state.resume_text,
                                jd,
                                scorecard.gaps,
                                override=(
                                    scorecard.verdict
                                    == "skip"
                                )
                            )
                        )

                        # fallback safety
                        if sugg is None:
                            sugg = {
                                "paraphrasing": [],
                                "missing": []
                            }

                        st.session_state.suggestions = sugg

                    except Exception as e:

                        st.error(
                            f"Suggestion generation failed: {str(e)}"
                        )

                        st.session_state.suggestions = {
                            "paraphrasing": [],
                            "missing": []
                        }

        # -----------------------
        # Save History
        # -----------------------

        with col2:

            if st.button(
                "💾 Save to History",
                use_container_width=True
            ):

                entry = HistoryEntry(
                    jd_id=str(
                        uuid.uuid4()
                    )[:8],

                    analyzed_at=datetime.now(),

                    goal_set_id=
                    active_gs.id,

                    goal_set_name=
                    active_gs.name,

                    goal_set_snapshot=[
                        g.to_dict()
                        for g
                        in active_gs.goals
                    ],

                    resume_id="current",

                    resume_snapshot_hash=
                    analysis[
                        "resume_hash"
                    ],

                    scorecard=
                    scorecard.to_dict(),

                    verdict=
                    scorecard.verdict,

                    overall_fit=
                    scorecard.overall_fit,

                    status="pending",

                    jd_title=
                    jd.get(
                        "title",
                        "?"
                    ),

                    company=
                    jd.get(
                        "company",
                        "?"
                    ),

                    url=
                    jd.get("url")
                )

                st.session_state.history.append(
                    entry
                )

                save_history_locally()

                st.success(
                    "✓ Saved locally"
                )

        # -----------------------
        # DOWNLOAD FIXED
        # -----------------------

        with col3:

            if (
                "suggestions"
                in st.session_state
            ):

                sugg = (
                    st.session_state
                    .suggestions
                )

                output = (
                    "RESUME "
                    "IMPROVEMENT "
                    "SUGGESTIONS\n"
                )

                output += "=" * 50
                output += "\n\n"

                if sugg.get(
                    "paraphrasing"
                ):

                    output += (
                        "PARAPHRASE:\n"
                    )

                    for p in sugg[
                        "paraphrasing"
                    ]:

                        output += (
                            f"OLD: "
                            f"{p['original']}\n"
                        )

                        output += (
                            f"NEW: "
                            f"{p['improved']}\n\n"
                        )

                if sugg.get(
                    "missing"
                ):

                    output += (
                        "ADD TO "
                        "RESUME:\n"
                    )

                    for m in sugg[
                        "missing"
                    ]:

                        output += (
                            f"• "
                            f"{m['what_to_add']}\n"
                        )

                st.download_button(
                    label=
                    "📥 Download",
                    data=output,
                    file_name=
                    "suggestions.txt",
                    mime=
                    "text/plain",
                    use_container_width=True
                )

        # -----------------------
        # Suggestions View
        # -----------------------

        if (
            "suggestions"
            in st.session_state
            and show_suggestions
        ):

            sugg = (
                st.session_state
                .suggestions
            )
            # Fix None response
            if sugg is None:
                st.warning(
                    "No suggestions could be generated."
                )
                return

            if not isinstance(sugg, dict):
                st.error(
                    "Invalid suggestions response."
                )
                return

            st.divider()

            st.subheader(
                "Resume change suggestions"
            )

            if sugg.get(
                "paraphrasing"
            ):

                for p in sugg[
                    "paraphrasing"
                ]:

                    st.caption(
                        p.get(
                            "section",
                            "?"
                        )
                    )

                    st.markdown(
                        f"~~"
                        f"{p['original']}"
                        f"~~"
                    )

                    st.markdown(
                        f"→ "
                        f"{p['improved']}"
                    )

                    st.divider()

            if sugg.get(
                "missing"
            ):

                for m in sugg[
                    "missing"
                ]:

                    st.warning(
                        f"**"
                        f"{m.get('section','?')}"
                        f"** — "
                        f"{m['what_to_add']}"
                    )