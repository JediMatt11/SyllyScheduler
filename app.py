import os
import tempfile
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename
from ics import Calendar, Event
from dotenv import load_dotenv
load_dotenv()

from db import (
    insert_uploaded_file, insert_parsed_events, update_file_status,
    save_session, load_session, clear_session
)

import json
from openai import OpenAI
import PyPDF2

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(filepath):
    ext = filepath.rsplit(".", 1)[1].lower()

    if ext == "pdf":
        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text

    elif ext in ("doc", "docx"):
        import mammoth
        with open(filepath, "rb") as f:
            result = mammoth.extract_raw_text(f)
        return result.value

    elif ext in ("xls", "xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(filepath, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) for cell in row if cell is not None)
                if row_text.strip():
                    lines.append(row_text)
        return "\n".join(lines)

    else:
        raise ValueError(f"Unsupported file type: {ext}")


def parse_syllabus_with_ai(filepath, extra_instructions=""):
    syllabus_text = extract_text(filepath)

    user_instruction_block = (
        f"\nAdditional user instructions:\n{extra_instructions}\n"
        if extra_instructions else ""
    )

    prompt = f"""
You are an AI assistant that extracts academic schedule information from a syllabus.
{user_instruction_block}
Return ONLY valid JSON in this exact structure:

{{
  "events": [
    {{
      "name": "Event name",
      "begin": "YYYY-MM-DD HH:MM:SS",
      "end": "YYYY-MM-DD HH:MM:SS",
      "description": "Short description"
    }}
  ]
}}

Rules:
- If only a date is given, assume time is 00:00:00.
- If a time range is given, use it.
- If only a start time is given, set end time 1 hour later.
- Only include academic events (tests, quizzes, exams, deadlines).
- No commentary or explanation.

Syllabus text:
\"\"\"
{syllabus_text}
\"\"\"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("AI returned invalid JSON. Raw output:\n" + raw)

    if isinstance(data, dict):
        for key in ("events", "result", "data"):
            if key in data:
                events = data[key]
                break
        else:
            raise ValueError("AI JSON missing expected event list. Keys found: " + str(list(data.keys())))
    elif isinstance(data, list):
        events = data
    else:
        raise ValueError("Unexpected JSON structure: " + str(type(data)))

    if not isinstance(events, list):
        raise ValueError("Events field is not a list. Value: " + str(events))

    return events


def create_ics(events_data):
    c = Calendar()
    for item in events_data:
        e = Event()
        e.name = item['name']
        e.begin = item['begin']
        e.end = item['end']
        e.description = item.get('description', '')
        c.events.add(e)
    return c


def classify_event_type(event_name, description=""):
    text = f"{event_name} {description}".lower()

    if "exam" in text or "midterm" in text or "final" in text or "test" in text:
        return "Exam"
    elif "project" in text:
        return "Project"
    elif "homework" in text or "hw" in text or "assignment" in text:
        return "Homework"
    elif "quiz" in text:
        return "Quiz"
    elif "lab" in text:
        return "Lab"
    elif "discussion" in text:
        return "Discussion"
    elif "presentation" in text:
        return "Presentation"
    else:
        return "Other"


def transform_ai_events_for_db(events_data):
    db_events = []

    for item in events_data:
        begin_value = item.get("begin", "")
        event_date = begin_value.split(" ")[0] if begin_value else None

        if not event_date:
            continue

        title = item.get("name", "Untitled Event")
        description = item.get("description", "")
        event_type = classify_event_type(title, description)

        db_events.append({
            "title": title,
            "event_type": event_type,
            "event_date": event_date,
            "confidence_score": 0.85,
            "status": "draft"
        })

    return db_events


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    extra_instructions = request.form.get("extra_instructions", "")

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        file_type = filename.rsplit('.', 1)[1].lower()
        file_id = insert_uploaded_file(filename, file_type, "pending")

        try:
            events_data = parse_syllabus_with_ai(filepath, extra_instructions)

            raw_json = json.dumps(events_data, indent=2)
            save_session(raw_json)

            db_events = transform_ai_events_for_db(events_data)
            insert_parsed_events(file_id, db_events)
            update_file_status(file_id, "parsed")

            return jsonify({"status": "success"})

        except Exception as e:
            update_file_status(file_id, "failed")
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Invalid file type. Allowed types: PDF, DOC, XLS, XLSX"}), 400


@app.route('/confirm')
def confirm_page():
    return render_template('confirmation.html')


@app.route('/generate_ics', methods=['POST'])
def generate_ics_endpoint():
    req_data = request.get_json()
    events_data = req_data.get('events', [])

    try:
        calendar = create_ics(events_data)
        temp_ics = tempfile.NamedTemporaryFile(delete=False, suffix='.ics')
        with open(temp_ics.name, 'w') as f:
            f.writelines(calendar.serialize_iter())

        return send_file(
            temp_ics.name,
            as_attachment=True,
            download_name="SyllySchedule.ics",
            mimetype='text/calendar'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/success')
def success_page():
    return render_template('success.html')


@app.route('/raw_json')
def raw_json():
    data = load_session()
    return jsonify({"raw": data or ''})


@app.route('/session_status')
def session_status():
    data = load_session()
    return jsonify({"active": data is not None})


@app.route('/clear_session', methods=['POST'])
def clear_session_route():
    clear_session()
    return jsonify({"status": "cleared"})


if __name__ == '__main__':
    app.run(debug=True)
