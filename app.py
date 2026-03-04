from ai.chat_monitor import check_message
from ai.behaviour_analysis import calculate_trust_score, trust_level
from flask_cors import CORS

from flask import Flask, request, jsonify
import os
import json
    
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Load users from JSON file
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)
def load_logs():
    with open("logs.json", "r") as f:
        return json.load(f)
 

LOG_FILE = "logs.json"

def save_log(entry):
    logs = []

    if os.path.exists(LOG_FILE):
        # Check if file is not empty
        if os.path.getsize(LOG_FILE) > 0:
            with open(LOG_FILE, "r") as f:
                logs = json.load(f)
        else:
            logs = []   # empty file → start fresh

    logs.append(entry)

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=4)

# Save users to JSON file
def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)

def update_user_status(user):
    score = user["trust_score"]

    if score >= 60:
        user["status"] = "active"
    elif score >= 40:
        user["status"] = "warned"
    elif score >= 20:
        user["status"] = "blocked"
    else:
        user["status"] = "review"
def system_action(status):
    if status == "warned":
        return "User has been warned due to suspicious behavior"
    elif status == "blocked":
        return "User is temporarily blocked from chatting"
    elif status == "review":
        return "User flagged for admin review"
    else:
        return "No action required"


@app.route("/")
def home():
    return "Mentorin Backend Running Successfully!"

# REGISTER API
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    users = load_users()

    new_user = {
        "id": len(users) + 1,
        "name": data["name"],
        "email": data["email"],
        "password": data["password"],
        "role": data["role"],       # student or mentor
        "verified": False,
        "trust_score": 50,
        "status": "active" 
    }

    users.append(new_user)
    save_users(users)

    return jsonify({"message": "User registered successfully"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    users = load_users()

    for user in users:
        if user["email"] == data["email"] and user["password"] == data["password"]:

            safe_user = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "trust_score": user["trust_score"],
                "verified": user["verified"]
            }

            return jsonify({
                "message": "Login successful",
                "user": safe_user
            })

    return jsonify({"message": "Invalid email or password"}), 401

@app.route("/analyze_chat", methods=["POST"])
def analyze_chat():
    data = request.json
    users = load_users()

    user_id = data.get("user_id")
    message = data.get("message")

    if not user_id or not message:
        return jsonify({"message": "Invalid request data"}), 400

    user_id = int(user_id)

    # 🔥 AI MODULE
    ai_result = check_message(message)
    intent = ai_result.get("intent")

    severity = "low"
    score_change = 0
    block_message = False   # 🔴 NEW

    # ✅ Severity + score rules
    if intent == "professional":
        severity = "low"
        score_change = +2      # mentoring help → reward

    elif intent == "flirt":
        severity = "medium"
        score_change = -3  
        block_message = True    # small warning

    elif intent in ["abusive", "scam", "unethical", "manipulative"]:
        severity = "high"
        score_change = -15
        block_message = True   # 🚫 BLOCK

    for user in users:
        if user["id"] == user_id:

            # 🚫 already blocked user
            if user["status"] == "blocked":
                return jsonify({
                    "message": "User is blocked due to repeated policy violations",
                    "status": "blocked"
                }), 403

            # 🔄 Update trust score
            user["trust_score"] = max(
                0, min(100, user["trust_score"] + score_change)
            )

            # 🔄 Update status
            update_user_status(user)
            action = system_action(user["status"])
            save_users(users)

            # 📝 Log
            save_log({
                "user_id": user_id,
                "intent": intent,
                "severity": severity,
                "trust_score_change": score_change,
                "new_trust_score": user["trust_score"],
                "status": user["status"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # 🚫 BLOCK RESPONSE
            if block_message:
                return jsonify({
                    "message": "Message blocked due to policy violation",
                    "intent": intent,
                    "severity": severity,
                    "status": user["status"]
                }), 403

            # ✅ ALLOW RESPONSE
            return jsonify({
                "message": "Chat analyzed successfully",
                "intent": intent,
                "severity": severity,
                "updated_trust_score": user["trust_score"],
                "trust_level": trust_level(user["trust_score"]),
                "status": user["status"],
                "system_action": action
            })

    return jsonify({"message": "User not found"}), 404

@app.route("/analytics/trust/<int:user_id>", methods=["GET"])
def trust_analytics(user_id):
    logs = load_logs()
    history = []

    for log in logs:
        if log["user_id"] == user_id:
            history.append({
                "intent": log["intent"],
                "severity": log["severity"],
                "trust_score_change": log["trust_score_change"],
                "new_trust_score": log["new_trust_score"],
                "status": log["status"],
                "timestamp": log["timestamp"]
            })

    return jsonify({
        "user_id": user_id,
        "total_events": len(history),
        "current_trust_score": history[-1]["new_trust_score"] if history else "N/A",
        "trust_history": history
    })
@app.route("/analytics/all", methods=["GET"])
def all_analytics():
    users = load_users()

    mentors = []
    for user in users:
        if user["role"] == "mentor":
            mentors.append({
                "id": user["id"],
                "name": user["name"],
                "trust_score": user["trust_score"],
                "status": user["status"]
            })

    return jsonify(mentors)


if __name__ == "__main__":
    app.run(debug=True)

