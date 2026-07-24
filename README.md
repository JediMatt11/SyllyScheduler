# SyllyScheduler

SyllyScheduler is a web application designed to streamline academic organization by automatically parsing course syllabi and generating ready-to-import calendar files (`.ics`). By leveraging AI for text extraction and classification, students can instantly convert complex PDF schedules into actionable events for Google Calendar, Apple Calendar, or Outlook.

## 🚀 Features
* **Automated Parsing:** Upload a PDF syllabus and automatically extract exams, quizzes, labs, and homework deadlines.
* **Smart Classification:** Events are intelligently categorized and formatted using OpenAI's GPT models.
* **Interactive Editor:** Review, add, edit, or remove extracted events in a clean GUI before finalizing.
* **Universal Export:** One-click downloads to `.ics` format with seamless routing to major calendar applications.

## 🛠 Tech Stack
* **Frontend:** HTML5, CSS3, Vanilla JavaScript (Fetch API)
* **Backend:** Python, Flask
* **Database:** MySQL
* **APIs & Libraries:** OpenAI API, `PyPDF2` (text extraction), `ics` (calendar generation)

## 📁 Directory Structure

```text
root/
├── static/           # Contains all CSS, JavaScript, and image assets for the frontend UI.
├── templates/        # Contains all HTML templates (index.html, confirmation.html, success.html).
├── uploads/          # Temporary storage directory for files uploaded by users prior to parsing.
├── app.py            # Main Flask application controller and routing logic.
├── db.py             # Database connection and MySQL CRUD operations.
├── requirements.txt  # Python package dependencies.
└── .env              # (Not tracked) Environment variables for DB and API credentials.
```
## Setup

### Install Dependancies
`pip install -r requirements.txt`

### Configure Environment Variables

* Create a `.env` file in the root directory and add your database and API credentials:

```
OPENAI_API_KEY=your_openai_api_key
DB_HOST=localhost
DB_USER=your_db_username
DB_PASSWORD=your_db_password
DB_NAME=syllyscheduler_db
