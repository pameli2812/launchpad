# AI Resume Analyzer

A Streamlit app that analyzes resumes against a job description using semantic matching and OpenAI.

## Setup

1. Create a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Add your OpenAI API key to `.env`:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   ```

4. Run the app:
   ```bash
   streamlit run app.py
   ```

## Project structure

- `app.py`: Streamlit interface
- `utils/parser.py`: Resume text extraction from PDF/DOCX
- `utils/matcher.py`: Resume/job description similarity scoring
- `utils/openai_helper.py`: OpenAI resume analysis helper
- `utils/ats_checker.py`: ATS friendliness checks
- `utils/recommendation.py`: Recommendation logic
