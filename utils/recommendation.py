def recommend_action(score):
    if score > 80:
        return "Strongly recommended to apply."
    if score > 65:
        return "Can apply with improvements."
    return "Needs significant resume updates before applying."
