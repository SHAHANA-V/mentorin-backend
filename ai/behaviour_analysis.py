def calculate_trust_score(current_score, change):
    new_score = current_score + change
    return max(0, min(100, new_score))


def trust_level(score):
    if score >= 80:
        return "High Trust"
    elif score >= 50:
        return "Medium Trust"
    else:
        return "Low Trust"
