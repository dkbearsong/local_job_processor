# Job Matcher & Resume Optimizer

This application is an AI-powered tool designed to analyze job descriptions, extract key requirements, and compare them against a user's resume and profile. It provides a ranked list of matching jobs and actionable suggestions for adjusting a resume to better fit specific roles.

**Now featuring a modern web interface powered by FastAPI and React!**

## 📋 Prerequisites

Before running the application, ensure you have the following installed:
- **Python 3.10+**
- **Node.js & npm** (For the React frontend)
- **Pip** (Python package manager)
- **LM Studio** (Running locally with an OpenAI-compatible server enabled)
- **Access to Google Gemini API** (For production mode)
- **PostgreSQL DB**


# Job Matcher & Resume Optimizer

This application is an AI-powered tool designed to analyze job descriptions, extract key requirements, and compare them against a user's resume and profile. It provides a ranked list of matching jobs and actionable suggestions for adjusting a resume to better fit specific roles.

**Now featuring a modern web interface powered by FastAPI and React!**

## 📋 Prerequisites

Before running the application, ensure you have the following installed:
- **Python 3.10+**
- **Node.js & npm** (For the React frontend)
- **Pip** (Python package manager)
- **LM Studio** (Running locally with an OpenAI-compatible server enabled)
- **Access to Google Gemini API** (For production mode)
- **PostgreSQL DB**

### Installation

1. Clone this repository or download the source files.
2. **Backend Setup**: Install the required Python dependencies by running `pip install -r requirements.txt`
3. Set up .env file as shown in the [Configuration (`.env`) section](#env)
4. **Backend Setup**: Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   ```

## ⚙️ Configuration (`.env`) {#env}

The application relies on a `.env` file for all sensitive credentials and file paths. Create a file named `.env` in the root directory and configure it as follows:

### 1. LLM Settings
- `GEMINI_KEY`: Your Google Gemini API key (Required for production).
- `LM_STUDIO_API`: The base URL for your local LM Studio instance (e.g., `http://127.0.0.1`).
- `LM_STUDIO_PORT`: The port LM Studio is running on (e.g., `1234`).
- `LM_STUDIO_MODEL`: The specific model name loaded in LM Studio. (models like gemma4 or Qwen3.6 are recommended for best results)

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

## CSV
For csv import, you need a total of 4 fields:

- id: A unique identifier for the job record
- job_name: The name of the job
- company_name: The name of the company
- job_summary: A job description


## 🚀 Running the Application

To run the full application, you need to start both the backend and the frontend.

### 1. Start the Backend
Navigate to the root directory and start the FastAPI server:

#### On macOS/Linux
```bash
source .venv/bin/activate   

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### On Windows
```powershell
.venv\Scripts\activate     

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Frontend
In a **new terminal**, navigate to the `frontend/` directory and run Vite:
```bash
cd frontend
npm run dev
```

### 3. Access the UI
Open your browser to the URL provided by Vite (typically `http://localhost:5173`). 

**Usage Tips:**
- **LM Studio Settings**: You can override the default LM Studio endpoint directly from the UI via the settings gear in the header.
- **Input Modes**: Use the form to switch between **SQL DB** mode and **CSV Upload** mode.
- **Search**: You can search by Job Title or Company, and adjust the "Days Back" and "Limit" parameters directly in the web interface.

## 📄 Output

The application generates a `.docx` report (via `generate_job_report`) containing:
- **Market Insights**: Common skills, responsibilities, and requirements found in the searched job pool.
- **Suggested Projects**: AI-generated project ideas to help build relevant skills.
- **Job Matches**: A ranked list of jobs from your database with match scores and reasoning.
- **Resume Adjustments**: Specific suggestions on how to tailor your resume for the top matching roles.

The web interface includes a **Download .docx** button to retrieve these reports instantly.

## Scraping
 This tool presumes you have a way to scrape the jobs you want to sort through and format them as you wish, and does not do web scraping for you. I use a mix of tools including an aumated scraping microservice [found here](https://github.com/dkbearsong/web_scraper) and a browser extension called [Easy Scraper](https://chromewebstore.google.com/detail/easy-scraper-one-click-we/cljbfnedccphacfneigoegkiieckjndh) for sites that are too pernicious.