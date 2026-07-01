import os
import uuid
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify

# Import rate limiting dependencies
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import variables and functions from your custom pipeline configuration
from config import GROQ_API_KEY, LLM_MODEL, LOG_FILE, VALID_ATTRIBUTIONS
from utils import calculate_confidence_score, generate_transparency_label
from signals import get_LLM_score, get_stylometric_score

app = Flask(__name__)

# Initialize Limiter using your memory storage configuration strategy
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

def init_db():
    """Initializes the SQLite database with the strict audit log schema."""
    db_dir = os.path.dirname(LOG_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    with sqlite3.connect(LOG_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                content_id TEXT,
                creator_id TEXT,
                timestamp TEXT,
                attribution TEXT,
                confidence REAL,
                llm_score TEXT,
                stylometric_score TEXT,
                status TEXT,
                creator_reasoning TEXT
            )
        """)
        conn.commit()

init_db()


def log_event(entry):
    """Appends a new comprehensive record entry into the SQLite audit log database."""
    with sqlite3.connect(LOG_FILE) as conn:
        conn.execute(
            "INSERT INTO audit_log VALUES (:content_id, :creator_id, :timestamp, "
            ":attribution, :confidence, :llm_score, :stylometric_score, :status, :creator_reasoning)",
            {
                **entry, 
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
        )
        conn.commit()


def read_log(limit=20):
    """Reads historical data array rows structured directly into dictionaries."""
    with sqlite3.connect(LOG_FILE) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


# ===========================================================================
# WEB API ENDPOINTS
# ===========================================================================

@app.route("/")
def home():
    """Base template landing route confirming engine availability."""
    return "Provenance Guard is running."


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute; 25 per day")
def submit():
    """
    Submission flow execution endpoint. Evaluates text via multi-signal 
    scoring metrics, handles degradation defaults, generates layout text, and logs.
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    creator_id = data.get("creator_id", "anonymous")

    if not text:
        return jsonify({"error": "Missing required body parameter: text"}), 400

    # 1. Execute Underlying Signals
    llm_res = get_LLM_score(text)
    raw_llm_score = llm_res.get("llm_score", -1.0)
    llm_reasoning = llm_res.get("llm_reasoning", "No descriptive reasoning available.")
    raw_sty_score = get_stylometric_score(text)

    is_llm_valid = (0.0 <= raw_llm_score <= 1.0)
    is_sty_valid = (0.0 <= raw_sty_score <= 1.0)

    content_id = str(uuid.uuid4())

    # 2. Score Metrics & Grading Paths
    if is_llm_valid and is_sty_valid:
        # Fixed: calculate result dict and read keys to prevent assignment errors
        pipeline_res = calculate_confidence_score(raw_llm_score, raw_sty_score)
        confidence = pipeline_res["confidence_score"]
        
        orig_attr = pipeline_res["attribution"]
        if orig_attr == "likely-human":
            attribution = "likely human-written"
        elif orig_attr == "likely-AI":
            attribution = "likely AI-generated"
        else:
            attribution = "uncertain"
            
        log_llm = raw_llm_score
        log_sty = raw_sty_score
        
    elif is_llm_valid or is_sty_valid:
        confidence = raw_llm_score if is_llm_valid else raw_sty_score
        
        # Fallback grading matrix parameters
        if 0.0 <= confidence < 0.45:
            attribution = "likely human-written"
        elif 0.45 <= confidence <= 0.65:
            attribution = "uncertain"
        else:
            attribution = "likely AI-generated"
            
        log_llm = raw_llm_score if is_llm_valid else "NaN"
        log_sty = raw_sty_score if is_sty_valid else "NaN"
    else:
        return jsonify({"error": "All validation signals returned unreadable metrics."}), 500

    if attribution not in VALID_ATTRIBUTIONS:
        attribution = "uncertain"

    # 3. Text Generation Layout Setup
    label = generate_transparency_label(
        attribution=attribution,
        llm_score=raw_llm_score if is_llm_valid else 0.5,
        stylometric_score=raw_sty_score if is_sty_valid else 0.5,
        reasoning=llm_reasoning
    )

    # 4. Commit Structured Event Record Map
    log_event({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": str(log_llm),
        "stylometric_score": str(log_sty),
        "status": "classified",
        "creator_reasoning": None
    })

    return jsonify({
        "content_id": content_id,
        "confidence": confidence,
        "attribution": attribution,
        "label": label
    }), 200


@app.route("/appeal", methods=["POST"])
@limiter.limit("10 per minute; 25 per day")
def appeal():
    """Appeals Workflow endpoint. Duplicates historical entries to mark them as under review."""
    data = request.get_json() or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning", "")

    if not content_id:
        return jsonify({"error": "Missing required lookup parameter: content_id"}), 400

    with sqlite3.connect(LOG_FILE) as conn:
        conn.row_factory = sqlite3.Row
        original_entry = conn.execute(
            "SELECT * FROM audit_log WHERE content_id = ? ORDER BY timestamp DESC LIMIT 1", 
            (content_id,)
        ).fetchone()

    if not original_entry:
        return jsonify({"error": "No matching database records found for content_id reference."}), 404

    log_event({
        "content_id": original_entry["content_id"],
        "creator_id": original_entry["creator_id"],
        "attribution": original_entry["attribution"],
        "confidence": original_entry["confidence"],
        "llm_score": original_entry["llm_score"],
        "stylometric_score": original_entry["stylometric_score"],
        "status": "under review",
        "creator_reasoning": creator_reasoning
    })

    return jsonify({
        "content_id": content_id,
        "status": "under review",
        "message": "Your appeal was received and is under review.",
    }), 200


@app.route("/log", methods=["GET"])
@limiter.limit("10 per minute; 50 per day")
def view_log():
    """Returns historical log tracking array structured data maps."""
    return jsonify({"entries": read_log()}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)