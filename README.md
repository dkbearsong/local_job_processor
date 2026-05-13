# Job Matcher & Resume Optimizer

This application is an AI-powered tool designed to analyze job descriptions, extract key requirements, and compare them against a user's resume and profile. It provides a ranked list of matching jobs and actionable suggestions for adjusting a resume to better fit specific roles.

## 📋 Prerequisites

Before running the application, ensure you have the following installed:
- **Python 3.10+**
- **Pip** (Python package manager)
- **LM Studio** (Running locally with an OpenAI-compatible server enabled)
- **Access to Google Gemini API** (For production mode)
- **PostgreSQL DB**

### Installation

1. Clone this repository or download the source files.
2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Configuration (`.env`)

The application relies on a `.env` file for all sensitive credentials and file paths. Create a file named `.env` in the root directory and configure it as follows:

### 1. LLM Settings
- `GEMINI_KEY`: Your Google Gemini API key (Required for production).
- `LM_STUDIO_API`: The base URL for your local LM Studio instance (e.g., `http://127.0.0.1`).
- `LM_STUDIO_PORT`: The port LM Studio is running on (e.g., `1234`).
- `LM_STUDIO_MODEL`: The specific model name loaded in LM Studio. My suggestion is gemma-4 26b or a simlar model if you can run it.

### 2. SSH & Database Credentials
*These are used by the `postgres_ssh_connector` to access your remote database.*
- `SSH_HOST`, `SSH_PORT`, `SSH_USERNAME`, `SSH_PASSWORD`, `SSH_KEY_PATH`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

### 3. File Paths
- `RESUME`: The absolute path to your resume file (`.pdf`, `.docx`, or `.txt`).
- `PROFILE`: The absolute path to your user profile text file.

### 4. Application Mode
- `APP_MODE`: Set to `production` to run the full logic with real database queries and Gemini API calls. Set to `test` to use mock data for testing the workflow without hitting external APIs or databases.

## ⚙️ Configuration (SQL DB)
- The current iteration of this application requires a SQL DB that stores records for jobs that are scraped from various platforms. It's written for Postgres, so there may be some issues if the DB is in a different language. Future versions will allow usage of Postgres or csv for import.

In the meantime, in order for the Postgres DB query to run, the following tables and fields need to be set and data scraped to these:

**Table: job**
- id (pkey) <int>
- job_name <varchar1000>
- company_id (fkey) <int>
- office_id (fkey) <int>
- skip <boolean>
- summary <text>
- date_added <date>
**Table: company**
- id (pkey) <int>
- company_name <varchar255>
**Table: office**
- id (pkey) <int>
- country <varchar255>
- location <varchar255>


## 🚀 Running the Application

To start the process, run the following command in your terminal:

```bash
python main.py
```

### User Input (Production Mode)
When running in `production` mode, the script will prompt you for:
1. **Job Title**: The title to search for in the database.
2. **Days Back**: How many days of job postings to look through.
3. **Limit**: The number of matching jobs to pull from the database.
4. **Top Jobs Count**: How many top matches to display in the final report.

## 📄 Output

The application generates a `.docx` report (via `generate_job_report`) containing:
- **Market Insights**: Common skills, responsibilities, and requirements found in the searched job pool.
- **Suggested Projects**: AI-generated project ideas to help build relevant skills.
- **Job Matches**: A ranked list of jobs from your database with match scores and reasoning.
- **Resume Adjustments**: Specific suggestions on how to tailor your resume for the top matching roles.
