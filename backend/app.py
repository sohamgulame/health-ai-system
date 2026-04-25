import os
import json
import traceback
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
from openai import OpenAI
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
load_dotenv()

# Point Flask to the new frontend directory
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(base_dir, '..', 'frontend')

app = Flask(__name__, 
            template_folder=os.path.join(frontend_dir, 'templates'),
            static_folder=os.path.join(frontend_dir, 'static'))
app.secret_key = os.getenv("SECRET_KEY", "super-secret-key-for-health-ai")
CORS(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# NVIDIA Configuration
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "health_db")
        )
    except mysql.connector.Error as err:
        print(f"DB Connection Error: {err}")
        return None

def analyze_with_ai(temperature, heart_rate, spo2):
    prompt = f"""You are an expert clinical medical assistant AI. Based on the following real-time physiological readings:
Temperature: {temperature} °C
Heart Rate: {heart_rate} bpm
SpO2: {spo2} %

Provide professional clinical analysis with these exact sections (2-3 sentences each):
- prediction: Overall health status (Healthy, Monitor, Caution, or Critical).
- diagnosis: List 2-3 possible conditions that could explain these readings with likelihood (e.g., "Fever (high), Infection (medium), Inflammation (low)").
- explanation: Key findings - what each reading indicates about the patient's condition.
- advice: 3-4 specific, actionable health recommendations.

Return ONLY a valid JSON string with these exactly keys: "prediction", "diagnosis", "explanation", "advice" and no markdown or extra formatting."""
    
    try:
        response = client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
            stream=False
        )
        
        text = response.choices[0].message.content.strip()
        
        # Remove markdown formatting if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        parsed = json.loads(text.strip())
        
        # Ensure all fields are strings, not lists or dicts, for MySQL compatibility
        for key in ["advice", "prediction", "explanation", "diagnosis"]:
            val = parsed.get(key)
            if isinstance(val, list):
                parsed[key] = "\n".join(str(item) for item in val)
            elif isinstance(val, dict):
                parsed[key] = json.dumps(val)
            else:
                parsed[key] = str(val) if val is not None else "N/A"
            
        return parsed
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        if 'text' in locals() and text:
            print(f"Raw response text: {text}")
        traceback.print_exc()
        return {
            "prediction": "Unable to assess",
            "diagnosis": "Analysis pending",
            "explanation": f"Error retrieving analysis: {str(e)}",
            "advice": "Please try again or consult a healthcare professional"
        }

@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for("reading_page"))
    return redirect(url_for("login_page"))

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = db.cursor()
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            return jsonify({"error": "Username or Email already exists"}), 400

        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                       (username, email, password_hash))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": "User created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing fields"}), 400

    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({"message": "Login successful", "username": user['username']}), 200
        else:
            return jsonify({"error": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/home")
@app.route("/dashboard")
@login_required
def home():
    return redirect(url_for("reading_page"))

@app.route("/index")
@login_required
def index_redirect():
    return redirect(url_for("reading_page"))

@app.route("/reading")
@login_required
def reading_page():
    return render_template("reading.html")

@app.route("/manual-reading")
@login_required
def manual_reading_page():
    return render_template("manual-reading.html")

@app.route("/analysis")
@login_required
def analysis_page():
    return render_template("analysis.html")

@app.route("/report")
@login_required
def report_page():
    return render_template("report.html")

@app.route("/api/analyze", methods=["POST"])
def analyze_reading():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        temp = data.get("temperature")
        hr = data.get("heart_rate")
        spo2 = data.get("spo2")

        if temp is None or hr is None or spo2 is None:
            return jsonify({"error": "Missing required fields"}), 400
            
        # Get AI analysis
        ai_response = analyze_with_ai(temp, hr, spo2)
        
        # Save this analyzed reading as a permanent record
        db = get_db_connection()
        if db:
            cursor = db.cursor()
            user_id = session.get('user_id')
            sql = "INSERT INTO readings (user_id, temperature, heart_rate, spo2, prediction, diagnosis, explanation, advice) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            val = (user_id, temp, hr, spo2, 
                   str(ai_response.get("prediction", "N/A")), 
                   str(ai_response.get("diagnosis", "N/A")), 
                   str(ai_response.get("explanation", "N/A")), 
                   str(ai_response.get("advice", "N/A")))
            cursor.execute(sql, val)
            db.commit()
            cursor.close()
            db.close()
            
        return jsonify(ai_response), 200
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/health-data", methods=["POST"])
def receive_health_data():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        temp = data.get("temperature")
        hr = data.get("heart_rate")
        spo2 = data.get("spo2")

        if temp is None or hr is None or spo2 is None:
            return jsonify({"error": "Missing required fields"}), 400
            
        # Save to MySQL without AI analysis (Live update)
        db = get_db_connection()
        if db:
            cursor = db.cursor()
            # For live data from ESP32, we check if user_id is provided in the payload.
            # If not, we fall back to session user_id (for manual/web submissions).
            user_id = data.get('user_id') or session.get('user_id')
            
            sql = "INSERT INTO readings (user_id, temperature, heart_rate, spo2, prediction, advice) VALUES (%s, %s, %s, %s, %s, %s)"
            val = (user_id, temp, hr, spo2, "Live Monitoring", "Click Analyze for full report")
            cursor.execute(sql, val)
            db.commit()
            
            cursor.close()
            db.close()
            
        return jsonify({"message": "Data received successfully"}), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/latest-analysis", methods=["GET"])
def get_latest_analysis():
    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        cursor = db.cursor(dictionary=True)
        user_id = session.get('user_id')
        
        # Search specifically for the latest record with a diagnosis (analyzed) for this user
        cursor.execute("SELECT * FROM readings WHERE user_id = %s AND diagnosis IS NOT NULL AND diagnosis != '' ORDER BY id DESC LIMIT 1", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        db.close()
        
        if result and result.get("timestamp"):
            result["timestamp"] = result["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            
        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "No analyzed reports found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/latest", methods=["GET"])
def get_latest_data():
    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        cursor = db.cursor(dictionary=True)
        user_id = session.get('user_id')
        cursor.execute("SELECT * FROM readings WHERE user_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        db.close()
        
        # Ensure timestamp is string for JSON serialization
        if result and result.get("timestamp"):
            result["timestamp"] = result["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if result:
            # Add server time
            result["server_time"] = current_time
            # Values are now directly in the DB columns
            return jsonify(result)
        else:
            # If no data exists, return default empty state instead of 404 for better UI UX
            return jsonify({
                "temperature": "--",
                "heart_rate": "--",
                "spo2": "--",
                "prediction": "No data available",
                "diagnosis": "Waiting for data",
                "explanation": "Send data from ESP32 to get analysis",
                "advice": "Send data from ESP32 first.",
                "server_time": current_time
            })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/report", methods=["GET"])
def get_report_data():
    db = get_db_connection()
    if not db:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        user_id = session.get('user_id')
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        offset = (page - 1) * limit
        
        cursor = db.cursor(dictionary=True)
        
        # Get total count of ANALYZED readings for this user
        cursor.execute("SELECT COUNT(*) as total FROM readings WHERE user_id = %s AND diagnosis IS NOT NULL AND diagnosis != ''", (user_id,))
        total = cursor.fetchone()['total']
        
        # Fetch paginated ANALYZED data for this user
        cursor.execute("SELECT * FROM readings WHERE user_id = %s AND diagnosis IS NOT NULL AND diagnosis != '' ORDER BY id DESC LIMIT %s OFFSET %s", (user_id, limit, offset))
        results = cursor.fetchall()
        cursor.close()
        db.close()
        
        for r in results:
            if r.get("timestamp"):
                r["timestamp"] = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        
        total_pages = (total + limit - 1) // limit  # Ceiling division
        return jsonify({
            "data": results,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure templates directory exists for the user
    os.makedirs(os.path.join(frontend_dir, 'templates'), exist_ok=True)
    os.makedirs(os.path.join(frontend_dir, 'static'), exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
