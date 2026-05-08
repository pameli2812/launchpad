import streamlit as st
from utils.parser import extract_text_from_pdf, extract_text_from_docx
from utils.matcher import calculate_match
from utils.openai_helper import analyze_resume

st.set_page_config(
    page_title="AI Resume Analyzer",
    layout="wide"
)

st.title("AI Resume Analyzer & Job Match Advisor")

uploaded_resume = st.file_uploader(
    "Upload Resume",
    type=["pdf", "docx"]
)

jd_text = st.text_area(
    "Paste Job Description",
    height=300
)

if uploaded_resume and jd_text:
    resume_text = ""

    if uploaded_resume.name.endswith(".pdf"):
        resume_text = extract_text_from_pdf(uploaded_resume)
    elif uploaded_resume.name.endswith(".docx"):
        resume_text = extract_text_from_docx(uploaded_resume)

    with st.spinner("Analyzing Resume..."):
        score = calculate_match(resume_text, jd_text)

        st.subheader("Match Percentage")
        st.progress(min(int(score), 100))
        st.write(f"{score}% Match")

        if score > 80:
            st.success("Strongly Recommended to Apply")
        elif score > 65:
            st.warning("Can Apply with Improvements")
        else:
            st.error("Needs Significant Resume Updates")

        analysis = analyze_resume(resume_text, jd_text)

        st.subheader("AI Suggestions")
        st.write(analysis)
