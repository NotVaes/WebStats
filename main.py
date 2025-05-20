from flask import Flask, request, render_template, jsonify
from flask_cors import CORS
from datetime import datetime
from pathlib import Path
import json, os, requests, logging

app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(level=logging.INFO)

VISIT_LOG_FILE = Path("visits.json")
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1374191677270659102/V-XkVQnRcrTVc4Z0TTDnwjaSS32cSMSHRe_85nJJ8O2Jz-E6nhQhZPQyYo9fG4FOcFec"

def get_geo_info(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}").json()
        return {
            "city": res.get("city", "Unknown"),
            "country": res.get("country", "Unknown")
        }
    except:
        return {"city": "Unknown", "country": "Unknown"}

@app.route("/", methods=["GET"])
def home():
    return {"status": "ok", "message": "Tracker is live"}, 200


@app.route("/visit", methods=["POST"])
def track_visit():
    data = request.json
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    ua = request.headers.get('User-Agent', 'Unknown')
    referrer = request.referrer or "Unknown"
    geo = get_geo_info(ip)

    visit = {
        "page": data.get("page"),
        "time": datetime.utcnow().isoformat(),
        "userAgent": ua,
        "ip": ip,
        "referrer": referrer,
        "geo": geo
    }

    # Discord
    message = (
        f"📥 **New Visit**\n"
        f"**Page:** {visit['page']}\n"
        f"**Time:** {visit['time']}\n"
        f"**IP:** {ip} ({geo['city']}, {geo['country']})\n"
        f"**User-Agent:** {ua}\n"
        f"**Referrer:** {referrer}"
    )

    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        logging.warning(f"Failed to send Discord webhook: {e}")

    try:
        if VISIT_LOG_FILE.exists():
            visits = json.loads(VISIT_LOG_FILE.read_text())
        else:
            visits = []
        visits.append(visit)
        VISIT_LOG_FILE.write_text(json.dumps(visits, indent=2))
    except Exception as e:
        logging.error(f"Failed to write log file: {e}")

    logging.info(f"Logged visit: {visit}")
    return jsonify({"status": "ok"})

@app.route("/stats")
def stats():
    try:
        visits = json.loads(VISIT_LOG_FILE.read_text())
    except:
        visits = []

    return render_template("stats.html", visits=visits)

@app.route("/robots.txt")
def robots_txt():
    return "User-agent: *\nDisallow: /visit", 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(debug=True)
