def evaluate_ats_friendly(resume_text):
    issues = []

    if "experience" not in resume_text.lower():
        issues.append("Add an experience section with concrete achievement statements.")
    if "education" not in resume_text.lower():
        issues.append("Include an education section with relevant degrees or certifications.")
    if len(resume_text) < 200:
        issues.append("Add more detail so applicant tracking systems can match keywords.")

    return issues
