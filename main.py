from flask import Flask, request, render_template, jsonify, send_file
from flask_cors import CORS
from datetime import datetime, timedelta
from pathlib import Path
import json, os, requests, logging, csv, io

app = Flask(__name__)
CORS(app)

# Configuration
VISIT_LOG_FILE = Path("visits.json")
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1374191677270659102/V-XkVQnRcrTVc4Z0TTDnwjaSS32cSMSHRe_85nJJ8O2Jz-E6nhQhZPQyYo9fG4FOcFec"
ALERT_THRESHOLD = 100  # visits per minute

# Logging setup
logging.basicConfig(level=logging.INFO)

# Utilities

def load_visits():
    if VISIT_LOG_FILE.exists():
        try:
            return json.loads(VISIT_LOG_FILE.read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_visits(visits):
    VISIT_LOG_FILE.write_text(json.dumps(visits, indent=2))


def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        logging.warning("Discord webhook URL not set. Skipping notification.")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
    except Exception as e:
        logging.error(f"Webhook failed: {e}")


def alert_if_spike():
    now = datetime.utcnow()
    one_min_ago = now - timedelta(minutes=1)
    visits = load_visits()
    recent = [v for v in visits if datetime.fromisoformat(v['time']) >= one_min_ago]
    if len(recent) > ALERT_THRESHOLD:
        send_discord(f"🚨 Traffic spike! {len(recent)} visits in the last minute.")

# Routes

@app.route("/", methods=["GET"])
def home():
    return {"status": "ok", "message": "WebStats Tracker Running"}

@app.route("/visit", methods=["POST"])
def track_visit():
    data = request.json or {}
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    visit = {
        "page": data.get("page", "?"),
        "time": datetime.utcnow().isoformat(),
        "userAgent": request.headers.get('User-Agent', 'Unknown'),
        "ip": ip,
        "referrer": request.referrer or "-"
    }

    # Append and save
    visits = load_visits()
    visits.append(visit)
    save_visits(visits)
    logging.info(f"Logged visit: {visit}")

    # Notify and alert
    send_discord(f"📥 New Visit: {visit['page']} from {visit['ip']}")
    alert_if_spike()

    return {"status": "ok"}

@app.route("/stats", methods=["GET"])
def stats():
    visits = load_visits()
    # aggregate stats
    total = len(visits)
    by_page = {}
    for v in visits:
        by_page[v['page']] = by_page.get(v['page'], 0) + 1
    return render_template("stats.html", total=total, by_page=by_page, visits=visits)

@app.route("/export", methods=["GET"])
def export_csv():
    visits = load_visits()

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["time", "page", "ip", "userAgent", "referrer"])
    for v in visits:
        writer.writerow([v['time'], v['page'], v['ip'], v['userAgent'], v['referrer']])
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='visits.csv'
    )

@app.route("/robots.txt", methods=["GET"])
def robots_txt():
    return "User-agent: *\nDisallow: /visit", 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
