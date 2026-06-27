# COMP90024 Assignment 2 – Data Ingestion and Analytics Pipeline

## Project Overview

This project collects conflict-related social media posts and official oil price data, processes the data, stores it in Elasticsearch, and exposes the cleaned results through a FastAPI backend for notebook-based analysis and visualisation.

The current scenario focuses on Australian-related discussions of global conflicts, mainly Ukraine, Gaza and Iran, and compares social media sentiment with Brent and WTI crude oil price data.

The system uses:

- Mastodon and BlueSky social media data
- Official EIA crude oil spot price data
- Text cleaning and preprocessing
- TextBlob sentiment analysis
- Rule-based conflict classification
- Elasticsearch for storage and querying
- FastAPI for REST API access
- Jupyter Notebook for visualisation and analysis
- Docker Compose for local Elasticsearch setup
- Docker image packaging for the backend API
- Kubernetes for cloud deployment on Nectar
- Fission timer trigger for scheduled ingestion
- Kubernetes CronJob as a backup scheduled ingestion option

---

Repository Source

This repository was originally cloned from the University of Melbourne GitLab project:

git@gitlab.unimelb.edu.au:chenxuanjin/COMP90024_team_8.git

The current GitHub version is a cleaned and reorganised copy prepared for project portfolio presentation, with documentation updated to describe the system architecture, setup process, cloud deployment workflow, and implemented analytics pipeline.

---

## System Architecture

```text
Mastodon / BlueSky APIs + EIA oil price data
        ↓
Data collection
        ↓
Text cleaning and preprocessing
        ↓
Sentiment analysis and conflict classification
        ↓
Bulk ingestion into Elasticsearch
        ↓
FastAPI backend
        ↓
Notebook visualisation frontend
        ↓
Tables, charts and analytics results
```

Cloud scheduled ingestion uses this flow:

```text
Fission timer trigger
        ↓
Fission Python function
        ↓
POST /ingest/run on the FastAPI backend
        ↓
Existing ingestion pipeline
        ↓
Elasticsearch
```

The repository also includes a Kubernetes CronJob as an operational backup. The CronJob runs the same ingestion script directly from the backend Docker image.

---

## Repository Structure

```text
COMP90024_team_8-main/
├── backend/
│   ├── backendapimain.py         # FastAPI backend connected to Elasticsearch
│   ├── ingest_real_data.py       # Main real-data ingestion pipeline
│   ├── ingest_bulk.py            # Bulk ingestion test/helper script
│   ├── ingest_test.py            # Basic ingestion test script
│   └── query_summary.py          # Elasticsearch query summary script
│
├── data/
│   ├── media_cleaned.csv         # Local cleaned data backup
│   └── media_cleaned_from_api.csv
│
├── database/                     # Reserved for database-related files
├── frontend/
│   └── visualization.ipynb       # API-based visualisation notebook
│
├── fission/
│   └── trigger_ingestion.py      # Fission function that calls /ingest/run
│
├── k8s/
│   ├── api.yaml                  # FastAPI Kubernetes Deployment and Service
│   ├── elasticsearch.yaml        # Elasticsearch Kubernetes Deployment and Service
│   └── ingest-cronjob.yaml       # Kubernetes CronJob backup ingestion job
│
├── test/
│   ├── CCC90024ASSI2_API_modified.ipynb
│   ├── media_cleaned_from_api.csv
│   └── test.ipynb
│
├── Dockerfile                    # Backend API Docker image definition
├── docker-compose.yml            # Local Elasticsearch service
├── requirements.txt              # Backend Python dependencies
├── README.md
└── .gitignore
```

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://gitlab.unimelb.edu.au/chenxuanjin/COMP90024_team_8.git
cd COMP90024_team_8
```

If the repository is downloaded as a zip file, open the extracted project folder before running the commands below.

### 2. Install Backend Dependencies

The backend dependencies are listed in `requirements.txt`.

```bash
python -m pip install -r requirements.txt
```

On Windows with a specific Python 3.13 installation, use:

```powershell
& "C:\python313\python.exe" -m pip install -r requirements.txt
```

The visualisation notebooks may also require extra plotting and notebook libraries:

```bash
python -m pip install numpy matplotlib seaborn wordcloud praw ipython
```

### 3. Add API Credentials

For local ingestion, Mastodon credentials are expected in the project root directory:

```text
mastodon_clientcred.secret
mastodon_usercred.secret
```

The ingestion code reads these local default files unless environment variables are provided:

```text
MASTODON_CLIENTCRED_FILE
MASTODON_USERCRED_FILE
MASTODON_INSTANCE_URL
BLUESKY_IDENTIFIER
BLUESKY_PASSWORD
ES_URL
```

For Kubernetes deployment, the Mastodon credential files are mounted into the API and CronJob pods using the Kubernetes Secret named:

```text
mastodon-credentials
```

The cloud deployment expects these mounted paths:

```text
/app/mastodon_clientcred.secret
/app/mastodon_usercred.secret
```

BlueSky credentials should also be provided through environment variables or Kubernetes Secrets for a safer deployment.

Do not commit credential files, kubeconfig files, OpenStack RC files, GitLab tokens, `.pem` files, or local `.env` files.

---

## Running the Local Pipeline

### Step 1: Start Elasticsearch

Start Docker Desktop first, then run from the project root:

```bash
docker compose up -d
```

Check that Elasticsearch is available:

```bash
curl http://localhost:9200
```

Or open this URL in a browser:

```text
http://localhost:9200
```

The local Docker Compose file starts Elasticsearch 8.12.2 as a single-node service on port `9200`, with security disabled for the controlled academic prototype environment.

### Step 2: Run Data Ingestion

Run the main ingestion script:

```bash
python backend/ingest_real_data.py
```

On Windows with Python 3.13:

```powershell
& "C:\python313\python.exe" backend\ingest_real_data.py
```

This script:

- collects Mastodon posts
- collects BlueSky posts
- loads official EIA Brent and WTI crude oil price data
- cleans and standardises records
- calculates TextBlob sentiment scores
- classifies social media posts into Ukraine, Gaza and Iran conflict topics
- removes duplicate social media records using platform, date and text
- inserts records into Elasticsearch using the bulk API

The script uses the `ES_URL` environment variable when it is set. If `ES_URL` is not set, it connects to local Elasticsearch:

```text
http://localhost:9200
```

### Step 3: Check Elasticsearch Indexes

Open:

```text
http://localhost:9200/_cat/indices?v
```

Expected indexes:

```text
social_posts
market_prices
```

Example document counts from a local test run:

```text
social_posts     about 190 records
market_prices    about 2100+ records
```

The exact counts may change between ingestion runs because social media search results and EIA data availability can change.

---

## Running the FastAPI Backend Locally

Start the backend from the project root:

```bash
python -m uvicorn backend.backendapimain:app --reload
```

On Windows with Python 3.13:

```powershell
& "C:\python313\python.exe" -m uvicorn backend.backendapimain:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

The FastAPI documentation page is available at:

```text
http://127.0.0.1:8000/docs
```


---

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `/` | Returns backend status, Elasticsearch URL, index names, record counts and columns. |
| `/health` | Checks API status and Elasticsearch connection. |
| `/ingest/run` | Runs the ingestion pipeline and writes updated records into Elasticsearch. |
| `/posts` | Returns cleaned social media posts from Elasticsearch. |
| `/posts?limit=5` | Returns a limited number of posts. |
| `/posts?keyword=Gaza&limit=20` | Filters posts by keyword, clean text or conflict name. |
| `/posts/search?keyword=Gaza&limit=20` | Searches posts by keyword. |
| `/stats/platform` | Counts posts by platform. |
| `/stats/conflict` | Counts posts by conflict topic. |
| `/stats/sentiment` | Returns average sentiment by conflict topic. |
| `/stats/platform-sentiment` | Returns average sentiment by platform. |
| `/stats/timeline` | Returns daily post count and average sentiment. |
| `/stats/keywords` | Returns common keywords from cleaned post text. |
| `/stats/summary` | Returns a compact dataset summary. |
| `/market/prices` | Returns oil price records from Elasticsearch. |
| `/market/prices?benchmark=Brent&limit=20` | Filters market price records by benchmark. |
| `/market/latest?benchmark=Brent` | Returns the latest available price for the selected benchmark. |

Example checks:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/posts?limit=5
http://127.0.0.1:8000/posts/search?keyword=Gaza&limit=20
http://127.0.0.1:8000/stats/platform
http://127.0.0.1:8000/stats/conflict
http://127.0.0.1:8000/stats/sentiment
http://127.0.0.1:8000/stats/timeline
http://127.0.0.1:8000/stats/keywords
http://127.0.0.1:8000/market/prices?limit=5
http://127.0.0.1:8000/market/latest?benchmark=Brent
```

Manual ingestion endpoint test:

```powershell
Invoke-RestMethod -Method POST http://127.0.0.1:8000/ingest/run
```

Expected response shape:

```json
{
  "status": "completed",
  "message": "Ingestion completed successfully",
  "elasticsearch_url": "http://localhost:9200 or http://elasticsearch:9200",
  "social_index": "social_posts",
  "market_index": "market_prices"
}
```

---

## Running the Notebook Frontend

The main notebook frontend in the current repository is:

```text
frontend/visualization.ipynb
```

The `test/` folder also contains earlier or testing notebooks, including:

```text
test/CCC90024ASSI2_API_modified.ipynb
test/test.ipynb
```

Before running the visualisation notebook locally:

1. Start Elasticsearch with Docker Compose.
2. Run ingestion, or make sure the indexes already contain data.
3. Start the FastAPI backend by run 'kubectl port-forward svc/comp90024-api 8000:8000 -n comp90024'
4. Run the notebook cells.

The frontend notebook calls the local API endpoints such as:

```text
http://127.0.0.1:8000/posts?limit=10000
http://127.0.0.1:8000/market/prices?limit=10000
```

The notebook displays:

- social media post previews loaded from the API
- oil price records loaded from the API
- duplicate removal based on post URL
- word cloud of conflict-related posts
- platform-level post counts
- conflict topic counts
- sentiment score distributions
- platform and conflict sentiment comparisons
- daily post and sentiment trends
- Brent and WTI oil price comparison charts
- sentiment and oil price relationship charts

---

## Docker Image

The backend Docker image is built from `python:3.11-slim`.

The Dockerfile:

- sets `/app` as the working directory
- installs dependencies from `requirements.txt`
- copies the `backend/` source folder into the image
- starts the FastAPI app with Uvicorn on port `8000`

Build locally:

```bash
docker build -t comp90024-api .
```

Run the API container locally while using the host machine's Elasticsearch:

```bash
docker run --rm -p 8000:8000 \
  -e ES_URL=http://host.docker.internal:9200 \
  comp90024-api
```

For Kubernetes deployment, the manifests currently reference this GitLab Container Registry image:

```text
registry.gitlab.unimelb.edu.au:5005/chenxuanjin/comp90024_team_8/yaojinw-main-patch-25838:latest
```

Update `k8s/api.yaml` and `k8s/ingest-cronjob.yaml` if a different image path or tag is used.

---

## Cloud Deployment on Kubernetes

The Kubernetes deployment is intended to run in the namespace:

```text
comp90024
```

Main Kubernetes components:

- `elasticsearch`: Elasticsearch Deployment and ClusterIP Service
- `comp90024-api`: FastAPI backend Deployment and NodePort Service
- `mastodon-credentials`: Kubernetes Secret containing Mastodon credential files
- `gitlab-registry-secret`: image pull secret for the GitLab Container Registry
- `comp90024-ingestion-cronjob`: backup Kubernetes CronJob for scheduled ingestion

Set the kubeconfig path before running cloud commands. Example on Windows PowerShell:

```powershell
$env:KUBECONFIG="C:\path\to\kubeconfig\config"
```

Check cluster resources:

```powershell
kubectl get pods -n comp90024
kubectl get svc -n comp90024
```

Create the Mastodon credential secret if it does not already exist:

```powershell
kubectl create secret generic mastodon-credentials `
  --from-file=mastodon_clientcred.secret=./mastodon_clientcred.secret `
  --from-file=mastodon_usercred.secret=./mastodon_usercred.secret `
  -n comp90024
```

Create the GitLab registry pull secret if it does not already exist:

```powershell
kubectl create secret docker-registry gitlab-registry-secret `
  --docker-server=registry.gitlab.unimelb.edu.au:5005 `
  --docker-username=<your-gitlab-username> `
  --docker-password=<your-gitlab-token> `
  --docker-email=<your-email> `
  -n comp90024
```

Apply Elasticsearch and API manifests:

```powershell
kubectl apply -f k8s/elasticsearch.yaml -n comp90024
kubectl apply -f k8s/api.yaml -n comp90024
```

The API pod connects to Elasticsearch inside Kubernetes using:

```text
http://elasticsearch:9200
```

This value is passed through the `ES_URL` environment variable in `k8s/api.yaml`.

To test the cloud API locally, use port forwarding:

```powershell
kubectl port-forward svc/comp90024-api 8000:8000 -n comp90024
```

Then open:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

The API Service is also configured as a NodePort Service with node port `30080` in `k8s/api.yaml`.

---

## Fission Scheduled Ingestion

Fission is used as the serverless scheduled trigger layer for ingestion.

The Fission function source file is:

```text
fission/trigger_ingestion.py
```

The function sends an internal cluster request to:

```text
http://comp90024-api.comp90024.svc.cluster.local:8000/ingest/run
```

Final Fission flow:

```text
Fission timer: ingestion-daily
        ↓
Fission function: trigger-ingestion
        ↓
POST http://comp90024-api.comp90024.svc.cluster.local:8000/ingest/run
        ↓
FastAPI ingestion endpoint
        ↓
Elasticsearch
```

Check Fission:

```powershell
kubectl get pods -n fission
fission check
```

List the Fission environment, function and timer:

```powershell
fission environment list --namespace default
fission function list --namespace default
fission timer list --namespace default
```

Test the Fission function manually:

```powershell
fission function test --name trigger-ingestion --namespace default
```

Expected response shape:

```json
{"status":"completed","message":"Ingestion completed successfully","elasticsearch_url":"http://elasticsearch:9200","social_index":"social_posts","market_index":"market_prices"}
```

The intended Fission timer is:

```text
ingestion-daily
```

The intended schedule is once per day. If using the six-field Fission cron format with seconds, the schedule is:

```text
0 0 0 * * *
```

Check upcoming timer runs:

```powershell
fission timer showschedule --cron "0 0 0 * * *" --round 5
```

---

## Kubernetes CronJob Backup Ingestion

The repository also includes a Kubernetes CronJob manifest:

```text
k8s/ingest-cronjob.yaml
```

The CronJob directly runs:

```text
python backend/ingest_real_data.py
```

inside the backend Docker image.

It uses:

- the same Elasticsearch service: `http://elasticsearch:9200`
- the same Mastodon credential secret: `mastodon-credentials`
- the same GitLab image pull secret: `gitlab-registry-secret`

The CronJob schedule in the manifest is:

```text
0 0 * * *
```

This runs once per day at midnight according to the Kubernetes cluster timezone.

Apply the CronJob:

```powershell
kubectl apply -f k8s/ingest-cronjob.yaml -n comp90024
```

Create a manual test job from the CronJob:

```powershell
kubectl create job --from=cronjob/comp90024-ingestion-cronjob manual-ingestion-test -n comp90024
```

Check the job:

```powershell
kubectl get jobs -n comp90024
```

A successful run should show:

```text
Complete   1/1
```

The CronJob is kept as a backup because it is simple to debug through Kubernetes jobs and logs. The Fission timer is the main serverless scheduled trigger.

---

## Data Schema

### `social_posts`

```json
{
  "platform": "Mastodon",
  "date": "YYYY-MM-DD",
  "text": "...",
  "author": "...",
  "upvotes": 0,
  "url": "...",
  "sentiment_score": 0.0,
  "conflict": "Gaza Conflict",
  "clean_text": "..."
}
```

Possible conflict categories:

```text
Ukraine War
Gaza Conflict
Iran Tensions
```

Posts classified as `Other` are filtered out before insertion.

### `market_prices`

```json
{
  "date": "YYYY-MM-DD",
  "benchmark": "Brent",
  "price": 0.0
}
```

Possible benchmark values:

```text
Brent
WTI
```

The oil price loader keeps records from `2022-01-01` onward.

---

## Features Implemented

- Social media collection from Mastodon and BlueSky
- Official Brent and WTI oil price ingestion from EIA
- Text cleaning and preprocessing
- TextBlob sentiment scoring
- Rule-based classification for Ukraine, Gaza and Iran conflict topics
- Duplicate removal for social media posts
- Bulk ingestion into Elasticsearch
- Elasticsearch indexes for social posts and market prices
- FastAPI backend for posts, search, statistics, keywords and market prices
- `/ingest/run` endpoint for HTTP-triggered ingestion
- Notebook visualisation using REST API calls
- Local Elasticsearch setup through Docker Compose
- Docker image for backend deployment
- Kubernetes deployment on Nectar
- Kubernetes Secret mounting for Mastodon credential files
- Fission Python function and daily timer trigger for scheduled ingestion
- Kubernetes CronJob backup for scheduled ingestion

---

## Error Handling, Security and Reliability

Application-level error handling includes:

- Mastodon and BlueSky collection errors are caught during individual search loops.
- BlueSky login failure returns an empty DataFrame so the pipeline can continue where possible.
- The EIA loader tries multiple possible header rows before returning an empty schema.
- Date and numeric conversions use coercion to avoid crashes from malformed values.
- Backend data loaders return empty DataFrames with expected columns when Elasticsearch is empty or unreachable.
- `/health` reports whether Elasticsearch is reachable from the API container.

Security and deployment notes:

- Local Elasticsearch security is disabled because this is a controlled academic prototype.
- Mastodon credential files are excluded from Git and mounted through Kubernetes Secrets in the cloud.
- BlueSky credentials should be moved fully into environment variables or Kubernetes Secrets for production-quality security.
- The Docker image should not contain personal credential files, kubeconfig files, OpenStack RC files, GitLab tokens or `.pem` files.
- Kubernetes provides basic pod restart behaviour.
- The CronJob uses `concurrencyPolicy: Forbid`, `restartPolicy: OnFailure`, and `backoffLimit: 2`.

---

## Basic Local Run Checklist

```text
1. Start Docker Desktop.
2. Run: docker compose up -d
3. Open: http://localhost:9200
4. Add Mastodon credential files to the project root, or set credential environment variables.
5. Run: python backend/ingest_real_data.py
6. Open: http://localhost:9200/_cat/indices?v
7. Confirm social_posts and market_prices exist.
8. Run: python -m uvicorn backend.backendapimain:app --reload
9. Open: http://127.0.0.1:8000/health
10. Open: http://127.0.0.1:8000/posts?limit=5
11. Open: http://127.0.0.1:8000/market/prices?limit=5
12. Run frontend/visualization.ipynb.
```

---

## Basic Cloud Run Checklist

```text
1. Set KUBECONFIG.
2. Check: kubectl get pods -n comp90024
3. Ensure mastodon-credentials exists.
4. Ensure gitlab-registry-secret exists.
5. Apply: kubectl apply -f k8s/elasticsearch.yaml -n comp90024
6. Apply: kubectl apply -f k8s/api.yaml -n comp90024
7. Check: kubectl get pods -n comp90024
8. Test API: kubectl port-forward svc/comp90024-api 8000:8000 -n comp90024
9. Run: Invoke-RestMethod -Method POST http://127.0.0.1:8000/ingest/run
10. Check Fission: kubectl get pods -n fission and fission check
11. Test Fission: fission function test --name trigger-ingestion --namespace default
12. Check timer: fission timer list --namespace default
13. Apply the CronJob backup if needed: kubectl apply -f k8s/ingest-cronjob.yaml -n comp90024
14. Run the notebook against the forwarded or deployed API endpoint.
```

---

## Notes

- Docker Compose only starts local Elasticsearch. The FastAPI backend is started separately with Uvicorn during local development.
- In Kubernetes, Elasticsearch is reached through `http://elasticsearch:9200`.
- The backend reads up to 10,000 documents from each Elasticsearch index for API responses and statistics.
- Data is inserted using the Elasticsearch bulk API.
- Duplicate social media records are removed during ingestion using platform, date and text.
- The visualisation notebook should be run after Elasticsearch and FastAPI are both available.
- Fission is used for the serverless scheduled trigger, while Kubernetes CronJob is kept as an operational backup.
