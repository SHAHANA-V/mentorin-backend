import json
import os

BASE_DIR = os.path.dirname(__file__)
BAD_WORDS_FILE = os.path.join(BASE_DIR, "bad_words.json")

with open(BAD_WORDS_FILE, "r") as file:
    bad_words = json.load(file)

def check_message(message):
    message = message.lower()

    for category, words in bad_words.items():
        for word in words:
            if word in message:
                return {
                    "intent": category,   # abusive / scam / unethical
                    "confidence": "high"
                }

    # mentorship friendly default
    return {
        "intent": "professional",
        "confidence": "low"
    }

