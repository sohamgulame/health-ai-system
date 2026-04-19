import os
import json
import traceback
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

# Point Flask to the new frontend directory
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(base_dir, '..', 'frontend')

app = Flask(__name__, 
            template_folder=os.path.join(frontend_dir, 'templates'),
            static_folder=os.path.join(frontend_dir, 'static'))
CORS(app)

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
            database=os.getenv("DB_NAME", "health_iot_db")
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
        
        # Ensure all fields are strings, not lists
        for key in ["advice", "prediction", "explanation", "diagnosis"]:
            if isinstance(parsed.get(key), list):
                parsed[key] = "\n".join(str(item) for item in parsed[key])
            
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
    return render_template("login.html")

@app.route("/home")
@app.route("/dashboard")
def home():
    return redirect(url_for("reading_page"))

@app.route("/index")
def index_redirect():
    return redirect(url_for("reading_page"))

@app.route("/reading")
def reading_page():
    return render_template("reading.html")

@app.route("/manual-reading")
def manual_reading_page():
    return render_template("manual-reading.html")

@app.route("/analysis")
def analysis_page():
    return render_template("analysis.html")

@app.route("/report")
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
            sql = "INSERT INTO readings (temperature, heart_rate, spo2, prediction, diagnosis, explanation, advice) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            val = (temp, hr, spo2, 
                   ai_response.get("prediction", "N/A"), 
                   ai_response.get("diagnosis", "N/A"), 
                   ai_response.get("explanation", "N/A"), 
                   ai_response.get("advice", "N/A"))
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
            # We insert a 'live' record that doesn't have a diagnosis yet.
            # This makes it show on Live Reading but NOT in the permanent Health Records.
            sql = "INSERT INTO readings (temperature, heart_rate, spo2, prediction, advice) VALUES (%s, %s, %s, %s, %s)"
            val = (temp, hr, spo2, "Live Monitoring", "Click Analyze for full report")
            cursor.execute(sql, val)
            db.commit()
            
            # OPTIONAL: Delete older 'un-analyzed' readings to keep DB small
            # Only keep the last 50 raw readings or just the latest? Let's keep it simple for now.
            
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
        # Search specifically for the latest record with a diagnosis (analyzed)
        cursor.execute("SELECT * FROM readings WHERE diagnosis IS NOT NULL AND diagnosis != '' ORDER BY id DESC LIMIT 1")
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
        cursor.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 1")
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
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        offset = (page - 1) * limit
        
        cursor = db.cursor(dictionary=True)
        
        # Get total count of ANALYZED readings only
        cursor.execute("SELECT COUNT(*) as total FROM readings WHERE diagnosis IS NOT NULL AND diagnosis != ''")
        total = cursor.fetchone()['total']
        
        # Fetch paginated ANALYZED data
        cursor.execute("SELECT * FROM readings WHERE diagnosis IS NOT NULL AND diagnosis != '' ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset))
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
