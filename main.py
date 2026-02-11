from flask import Flask, request, jsonify
import requests, sqlite3, os
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def fetch_uuids(n=3):
    uuids = []
    for _ in range(n):
        try:
            resp = requests.get("https://httpbin.org/uuid", timeout=5)
            resp.raise_for_status()
            uuids.append(resp.json()["uuid"])
        except Exception as e:
            print(f"Fetch error: {e}")
    return uuids

def analyze_with_ai(uuid):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Provide 2-3 insights on this UUID. Classify sentiment as enthusiastic/critical/objective: {uuid}"
        response = model.generate_content(prompt)
        text = response.text.strip()
        sentiment = "objective"  # Improve parsing later
        if any(word in text.lower() for word in ["excited", "great"]):
            sentiment = "enthusiastic"
        elif any(word in text.lower() for word in ["bad", "poor"]):
            sentiment = "critical"
        return {"analysis": text[:200], "sentiment": sentiment}
    except Exception as e:
        return {"analysis": f"AI error: {str(e)}", "sentiment": "critical"}

def get_db():
    return sqlite3.connect("pipeline.db", check_same_thread=False)

def store_result(item):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO results VALUES (?, ?, ?, ?)", 
                  (datetime.utcnow().isoformat() + 'Z', item["original"], item["analysis"], item["sentiment"]))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def notify(email):
    try:
        with open("notification.log", "a") as f:
            f.write(f"Pipeline done for {email} at {datetime.utcnow().isoformat()}Z\n")
        return True
    except:
        return False

@app.before_first_request
def setup_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS results 
                 (timestamp TEXT, original TEXT, analysis TEXT, sentiment TEXT)''')
    conn.commit()
    conn.close()

@app.route("/pipeline", methods=["POST"])
def pipeline():
    data = request.json
    email = data.get("email", "default@example.com")
    
    items = []
    errors = []
    start_time = datetime.utcnow().isoformat() + 'Z'
    
    for uuid in fetch_uuids(3):
        try:
            ai = analyze_with_ai(uuid)
            stored = store_result({"original": uuid, "analysis": ai["analysis"], "sentiment": ai["sentiment"]})
            items.append({
                "original": uuid,
                "analysis": ai["analysis"],
                "sentiment": ai["sentiment"],
                "stored": stored,
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            })
        except Exception as e:
            errors.append(f"UUID {uuid}: {e}")
    
    notify(email)
    return jsonify({
        "items": items,
        "notificationSent": True,
        "processedAt": datetime.utcnow().isoformat() + 'Z',
        "errors": errors
    })

if __name__ == "__main__":
    app.run(debug=True)
