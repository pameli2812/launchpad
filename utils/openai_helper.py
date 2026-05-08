import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def analyze_resume(resume, jd):
    prompt = f"""
Analyze the resume against the job description.

Resume:
{resume}

Job Description:
{jd}

Provide:
1. Match summary
2. Missing skills
3. ATS suggestions
4. Resume improvements
5. Whether candidate should apply
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content
