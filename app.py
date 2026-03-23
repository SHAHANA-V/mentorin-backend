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
    score = user.get("trustScore", 50)

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


SIM_HISTORY_FILE = "simulationHistory.json"

def load_sim_history():
    if not os.path.exists(SIM_HISTORY_FILE):
        return []
    with open(SIM_HISTORY_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return []

def save_sim_history(history):
    with open(SIM_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

MOCK_SEQUENCE = [
    "Hi, I need help with learning React.",
    "Can you suggest a roadmap?",
    "What projects should I build to get hired?",
    "You guys are useless, just write the code for me."
]

@app.route("/")
def home():
    return "Mentorin Backend Running Successfully!"

# REGISTER API
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    users = load_users()

    # Validate email duplication
    if any(u.get("email") == data.get("email") for u in users):
        return jsonify({"message": "Email already registered"}), 400

    is_mentor = data.get("role") == "mentor"
    
    new_user = {
        "id": len(users) + 1,
        "name": data["name"],
        "email": data["email"],
        "password": data["password"],
        "role": data["role"],       # student or mentor
        "verified": False,
        "trustScore": 0 if is_mentor else 50,
        "status": "pending" if is_mentor else "active",
        "underReview": False
    }

    if is_mentor:
        new_user["skills"] = data.get("skills", "")
        new_user["experience"] = data.get("experience", "")
        new_user["domain"] = data.get("domain", "")
        new_user["bio"] = data.get("bio", "")
        new_user["linkedin"] = data.get("linkedin", "")

    users.append(new_user)
    save_users(users)

    return jsonify({"message": "User registered successfully"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    users = load_users()

    for user in users:
        if user.get("email") == data.get("email") and user.get("password") == data.get("password"):
            if user.get("status") == "pending":
                return jsonify({"message": "Account is pending admin approval"}), 403
            
            safe_user = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "trustScore": user.get("trustScore", 50),
                "verified": user.get("verified", False),
                "status": user.get("status", "active"),
                "underReview": user.get("underReview", False)
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

    # 🛡️ BANNED KEYWORD CHECK
    BANNED_KEYWORDS = ["abuse", "spam", "scam", "stupid", "idiot", "hate", "kill", "unethical"]
    message_lower = message.lower()
    
    is_unethical = any(word in message_lower for word in BANNED_KEYWORDS)

    warning_flag = False

    if is_unethical:
        intent = "unethical"
        severity = "high"
        score_change = -10
        block_message = False   # Requirement: STILL send message
        warning_flag = True
    else:
        # 🔥 AI MODULE
        try:
            ai_result = check_message(message)
            intent = ai_result.get("intent")
        except Exception:
            intent = "professional"

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
            block_message = False    # Do not auto block per new spec, just warn
            warning_flag = True

        elif intent in ["abusive", "scam", "unethical", "manipulative"]:
            severity = "high"
            score_change = -10
            block_message = False   
            warning_flag = True

    for user in users:
        if user.get("id") == user_id:

            # 🚫 check threshold block
            if user.get("status") == "blocked":
                return jsonify({
                    "message": "User is blocked due to repeated policy violations",
                    "status": "blocked"
                }), 403

            # 🔄 Update trust score
            current_score = user.get("trustScore", 50)
            new_score = max(0, min(100, current_score + score_change))
            user["trustScore"] = new_score

            # Auto Block logic (< 30)
            if new_score < 30:
                user["status"] = "blocked"
                user["underReview"] = True
            else:
                update_user_status(user)
                # Keep under review false if recovered somehow?
                if "underReview" not in user:
                    user["underReview"] = False

            action = system_action(user["status"])
            save_users(users)

            # 📝 Log
            save_log({
                "user_id": user_id,
                "intent": intent,
                "severity": severity,
                "trust_score_change": score_change,
                "new_trust_score": user["trustScore"],
                "status": user["status"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # 🚫 BLOCK RESPONSE (Only if block_message forcibly flagged, although we disabled above)
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
                "warning": warning_flag,
                "blocked": user["status"] == "blocked",
                "updated_trust_score": user["trustScore"],
                "trust_level": trust_level(user["trustScore"]),
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
        if user.get("role") == "mentor":
            mentors.append({
                "id": user.get("id"),
                "name": user.get("name"),
                "trustScore": user.get("trustScore", 50),
                "trust_score": user.get("trustScore", 50), # backward compatibility
                "status": user.get("status", "active")
            })

    return jsonify(mentors)


@app.route("/admin/users", methods=["GET"])
def admin_users():
    type_filter = request.args.get("type", "all")
    users = load_users()
    
    result = []
    for u in users:
        if u.get("role") != "admin":
            status = u.get("status")
            if type_filter == "all" or status == type_filter:
                result.append(u)
    return jsonify(result)

@app.route("/admin/mentor/action", methods=["POST"])
def admin_mentor_action():
    data = request.json
    users = load_users()
    user_id = int(data.get("user_id"))
    action = data.get("action")
    
    for user in users:
        if user["id"] == user_id:
            if action == "approve":
                user["status"] = "active"
                user["trustScore"] = 60
            elif action == "reject":
                users.remove(user)
            elif action == "unblock":
                user["status"] = "active"
                user["underReview"] = False
                user["trustScore"] = 30
            elif action == "ban":
                user["status"] = "banned"
            save_users(users)
            return jsonify({"message": f"User successfully {action}d"})
            
    return jsonify({"message": "User not found"}), 404

# 🤖 MOCK STUDENT SIMULATION ENGINE
@app.route("/admin/simulate/toggle", methods=["POST"])
def toggle_simulation():
    data = request.json
    users = load_users()
    user_id = int(data.get("user_id"))

    for user in users:
        if user["id"] == user_id:
            current_state = user.get("mockActive", False)
            user["mockActive"] = not current_state
            
            if user["mockActive"]: # Turning ON
                user["simulationData"] = {
                    "active": True,
                    "step": 0,
                    "history": [],
                    "metrics": {"prof_total": 0, "help_total": 0, "count": 0}
                }
                user["mockQueue"] = [MOCK_SEQUENCE[0]]
            else: # Turning OFF
                user["simulationData"] = {"active": False}
                user["mockQueue"] = []
                
            save_users(users)
            return jsonify({"message": "Simulation toggled", "mockActive": user["mockActive"]})
    return jsonify({"message": "User not found"}), 404

@app.route("/admin/simulate/trigger", methods=["POST"])
def trigger_simulation():
    data = request.json
    users = load_users()
    user_id = int(data.get("user_id"))
    msg_type = data.get("type", "professional")
    
    predefined = {
        "professional": "Can you guide me on learning React and preparing for interviews?",
        "technical": "I'm getting a CORS error when my React app calls Flask. How do I fix it?",
        "unethical": "You're an idiot, just tell me the answer now or else!"
    }
    
    message = predefined.get(msg_type, predefined["professional"])

    for user in users:
        if user["id"] == user_id:
            if "mockQueue" not in user:
                user["mockQueue"] = []
            user["mockQueue"].append(message)
            save_users(users)
            return jsonify({"message": "Mock message queued"})
    return jsonify({"message": "User not found"}), 404

@app.route("/chat/mock_sync/<int:user_id>", methods=["GET"])
def mock_sync(user_id):
    users = load_users()
    for user in users:
        if user["id"] == user_id:
            mock_active = user.get("mockActive", False)
            popped_msg = None
            
            # Pop the oldest message if queue has items
            if mock_active and user.get("mockQueue") and len(user["mockQueue"]) > 0:
                popped_msg = user["mockQueue"].pop(0)
                save_users(users)
                
            return jsonify({"mockActive": mock_active, "message": popped_msg})
            
    return jsonify({"mockActive": False, "message": None}), 404

@app.route("/admin/simulation/history", methods=["GET"])
def admin_simulation_history():
    return jsonify(load_sim_history())

@app.route("/simulate/reply", methods=["POST"])
def simulate_reply():
    data = request.json
    users = load_users()
    user_id = int(data.get("user_id"))
    msg = data.get("message", "")
    
    for user in users:
        if user["id"] == user_id:
            sim_data = user.get("simulationData", {})
            if not sim_data.get("active"):
                return jsonify({"error": "Simulation inactive"}), 400
                
            # NLP EVALUATION
            msg_lower = msg.lower()
            prof_score = 10
            help_score = 5
            
            # Length check
            if len(msg) > 20: help_score += 2
            
            # Helpful keywords
            if any(k in msg_lower for k in ["roadmap", "sure", "here", "learn", "guide", "project", "build", "try", "step", "first"]):
                help_score += 3
            
            # Professionalism breakdown
            unethical_words = ["stupid", "idiot", "fuck", "shut up", "useless", "dumb", "hate"]
            if any(w in msg_lower for w in unethical_words):
                prof_score -= 8
                
            # Bounds checking
            prof_score = max(0, min(10, prof_score))
            help_score = max(0, min(10, help_score))
            
            # Update metrics
            sim_data["metrics"]["prof_total"] += prof_score
            sim_data["metrics"]["help_total"] += help_score
            sim_data["metrics"]["count"] += 1
            
            # Inject history
            sim_data["history"].append({"sender": "Mentor", "text": msg})
            
            # Advance step
            sim_data["step"] += 1
            step = sim_data["step"]
            
            if step < len(MOCK_SEQUENCE):
                # Queue next reply natively
                next_msg = MOCK_SEQUENCE[step]
                sim_data["history"].append({"sender": "Aarav", "text": next_msg})
                if "mockQueue" not in user: user["mockQueue"] = []
                user["mockQueue"].append(next_msg)
                
                user["simulationData"] = sim_data
                save_users(users)
                return jsonify({"status": "ongoing", "next": next_msg})
            else:
                # SIMULATION COMPLETE — Generate rich report
                count = sim_data["metrics"]["count"]

                # Raw 0–10 averages
                raw_prof = sim_data["metrics"]["prof_total"] / count
                raw_help = sim_data["metrics"]["help_total"] / count

                # Sub-scores (each 0–100)
                communication_quality = round(raw_prof * 10, 1)
                response_accuracy     = round(raw_help * 10, 1)
                engagement_level      = round(min(100, (len(sim_data["history"]) / (len(MOCK_SEQUENCE) * 2)) * 100), 1)

                # Weighted final score (0–100)
                final_score = round(
                    (communication_quality * 0.4) +
                    (response_accuracy     * 0.4) +
                    (engagement_level      * 0.2),
                    1
                )

                # Tier assignment
                if final_score <= 50:
                    tier = "Needs Improvement"
                elif final_score <= 75:
                    tier = "Verified"
                else:
                    tier = "Trusted Mentor"

                report = {
                    "professionalism":      round(raw_prof, 1),
                    "helpfulness":          round(raw_help, 1),
                    "finalScore":           final_score,
                    "communicationQuality": communication_quality,
                    "responseAccuracy":     response_accuracy,
                    "engagementLevel":      engagement_level,
                    "verificationTier":     tier
                }
                
                # Format to absolute history driver
                hist_record = {
                    "mentorId": user_id,
                    "mentorName": user.get("name"),
                    "studentName": "Aarav",
                    "scores": report,
                    "history": sim_data["history"],
                    "timestamp": datetime.datetime.now().isoformat()
                }
                all_history = load_sim_history()
                all_history.append(hist_record)
                save_sim_history(all_history)
                
                # Cleanup user state
                user["mockActive"] = False
                user["simulationData"] = {"active": False, "report": report} # Leave report dangling for UI to snag
                user["mockQueue"] = []
                
                save_users(users)
                return jsonify({"status": "completed", "report": report})
                
    return jsonify({"error": "User not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)

