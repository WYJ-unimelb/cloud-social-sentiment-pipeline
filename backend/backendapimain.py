from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from collections import Counter
import re
from typing import Optional
from elasticsearch import Elasticsearch
import os

# Import ingestion functions for Fission/API-triggered ingestion.
# These functions reuse the same ingestion logic used by the Kubernetes CronJob.
from backend.ingest_real_data import ingest_social_posts, ingest_market_prices


app = FastAPI(title="COMP90024 Social Media Analytics API")

# Allow local notebook/browser clients to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Elasticsearch connection.
# Local default: http://localhost:9200
# Cloud/deployment use: set ES_URL environment variable.
ES_URL = os.getenv("ES_URL", "http://localhost:9200")
es = Elasticsearch(ES_URL)

SOCIAL_INDEX = "social_posts"
MARKET_INDEX = "market_prices"

STANDARD_COLUMNS = [
    "platform",
    "date",
    "text",
    "author",
    "upvotes",
    "url",
    "sentiment_score",
    "conflict",
    "clean_text",
]


def load_posts() -> pd.DataFrame:
    """
    Load social media posts from Elasticsearch.

    Expected Elasticsearch index:
    social_posts

    Expected fields:
    platform, date, text, author, upvotes, url,
    sentiment_score, conflict, clean_text
    """
    try:
        result = es.search(
            index=SOCIAL_INDEX,
            body={
                "query": {
                    "match_all": {}
                },
                "size": 10000
            }
        )

        records = [hit["_source"] for hit in result["hits"]["hits"]]
        df = pd.DataFrame(records)

        if df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)

        # Ensure all required columns exist.
        for column in STANDARD_COLUMNS:
            if column not in df.columns:
                df[column] = None

        # Type conversion.
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["sentiment_score"] = pd.to_numeric(df["sentiment_score"], errors="coerce")
        df["upvotes"] = pd.to_numeric(df["upvotes"], errors="coerce").fillna(0).astype(int)

        df["platform"] = df["platform"].fillna("Unknown").astype(str)
        df["conflict"] = df["conflict"].fillna("Unknown").astype(str)
        df["text"] = df["text"].fillna("").astype(str)
        df["clean_text"] = df["clean_text"].fillna("").astype(str)
        df["author"] = df["author"].fillna("").astype(str)
        df["url"] = df["url"].fillna("").astype(str)

        return df[STANDARD_COLUMNS]

    except Exception as e:
        print(f"Failed to load posts from Elasticsearch: {e}")
        return pd.DataFrame(columns=STANDARD_COLUMNS)


def load_market_prices() -> pd.DataFrame:
    """
    Load market price data from Elasticsearch.

    Expected Elasticsearch index:
    market_prices

    Expected fields:
    date, benchmark, price
    """
    try:
        result = es.search(
            index=MARKET_INDEX,
            body={
                "query": {
                    "match_all": {}
                },
                "size": 10000
            }
        )

        records = [hit["_source"] for hit in result["hits"]["hits"]]
        df = pd.DataFrame(records)

        if df.empty:
            return pd.DataFrame(columns=["date", "benchmark", "price"])

        for column in ["date", "benchmark", "price"]:
            if column not in df.columns:
                df[column] = None

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["benchmark"] = df["benchmark"].fillna("Unknown").astype(str)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

        return df[["date", "benchmark", "price"]]

    except Exception as e:
        print(f"Failed to load market prices from Elasticsearch: {e}")
        return pd.DataFrame(columns=["date", "benchmark", "price"])


def dataframe_to_records(df: pd.DataFrame):
    """Convert a DataFrame into JSON-safe records."""
    output = df.copy()

    if "date" in output.columns:
        output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    output = output.where(pd.notnull(output), None)
    return output.to_dict(orient="records")


@app.get("/")
def root():
    """Basic API status check."""
    df = load_posts()
    market_df = load_market_prices()

    try:
        es_connected = bool(es.ping())
    except Exception:
        es_connected = False

    return {
        "message": "COMP90024 Social Media Analytics API is running",
        "elasticsearch_url": ES_URL,
        "elasticsearch_connected": es_connected,
        "social_index": SOCIAL_INDEX,
        "market_index": MARKET_INDEX,
        "social_post_count": int(len(df)),
        "market_price_count": int(len(market_df)),
        "columns": df.columns.tolist(),
    }


@app.get("/health")
def health_check():
    """Simple health check endpoint for local or cloud deployment."""
    try:
        es_connected = bool(es.ping())
    except Exception:
        es_connected = False

    return {
        "status": "ok",
        "elasticsearch_connected": es_connected
    }


@app.post("/ingest/run")
def run_ingestion():
    """
    Trigger the existing ingestion workflow from inside the API container.

    This endpoint is designed for Fission timer invocation:
    Fission Timer -> Fission Function -> POST /ingest/run -> Elasticsearch.

    The API pod must have the same environment variables and mounted credentials
    as the Kubernetes CronJob:
    - ES_URL
    - MASTODON_CLIENTCRED_FILE
    - MASTODON_USERCRED_FILE
    """
    try:
        ingest_social_posts()
        ingest_market_prices()
        return {
            "status": "completed",
            "message": "Ingestion completed successfully",
            "elasticsearch_url": os.getenv("ES_URL", ES_URL),
            "social_index": SOCIAL_INDEX,
            "market_index": MARKET_INDEX,
        }
    except Exception as e:
        print(f"Ingestion endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {e}"
        )


@app.get("/posts")
def get_posts(
    limit: int = Query(default=100, ge=1, le=100000),
    keyword: Optional[str] = None,
):
    """
    Return cleaned social media posts from Elasticsearch.

    Examples:
    /posts?limit=20
    /posts?keyword=Gaza&limit=20
    """
    df = load_posts()

    if keyword:
        mask = (
            df["text"].astype(str).str.contains(keyword, case=False, na=False)
            | df["clean_text"].astype(str).str.contains(keyword, case=False, na=False)
            | df["conflict"].astype(str).str.contains(keyword, case=False, na=False)
        )
        df = df[mask]

    return dataframe_to_records(df.head(limit))


@app.get("/posts/search")
def search_posts(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(default=100, ge=1, le=100000),
):
    """
    Search cleaned posts by keyword.

    Example:
    /posts/search?keyword=Gaza&limit=20
    """
    df = load_posts()

    mask = (
        df["text"].astype(str).str.contains(keyword, case=False, na=False)
        | df["clean_text"].astype(str).str.contains(keyword, case=False, na=False)
        | df["conflict"].astype(str).str.contains(keyword, case=False, na=False)
    )

    result = df[mask].head(limit)
    return dataframe_to_records(result)


@app.get("/stats/platform")
def platform_stats():
    """Count posts by social media platform."""
    df = load_posts()

    if df.empty:
        return []

    result = (
        df.groupby("platform")
        .size()
        .reset_index(name="post_count")
        .sort_values("post_count", ascending=False)
    )

    return dataframe_to_records(result)


@app.get("/stats/conflict")
def conflict_stats():
    """Count posts by conflict topic."""
    df = load_posts()

    if df.empty:
        return []

    result = (
        df.groupby("conflict")
        .size()
        .reset_index(name="post_count")
        .sort_values("post_count", ascending=False)
    )

    return dataframe_to_records(result)


@app.get("/stats/sentiment")
def sentiment_stats():
    """Average sentiment score by conflict topic."""
    df = load_posts()

    if df.empty:
        return []

    result = (
        df.dropna(subset=["sentiment_score"])
        .groupby("conflict")["sentiment_score"]
        .mean()
        .reset_index()
        .rename(columns={"sentiment_score": "avg_sentiment"})
        .sort_values("avg_sentiment")
    )

    return dataframe_to_records(result)


@app.get("/stats/platform-sentiment")
def platform_sentiment_stats():
    """Average sentiment score by platform."""
    df = load_posts()

    if df.empty:
        return []

    result = (
        df.dropna(subset=["sentiment_score"])
        .groupby("platform")["sentiment_score"]
        .mean()
        .reset_index()
        .rename(columns={"sentiment_score": "avg_sentiment"})
        .sort_values("avg_sentiment")
    )

    return dataframe_to_records(result)


@app.get("/stats/timeline")
def timeline_stats():
    """Daily post count and daily average sentiment."""
    df = load_posts()

    if df.empty:
        return []

    df = df.dropna(subset=["date"]).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    result = (
        df.groupby("date")
        .agg(
            post_count=("text", "count"),
            avg_sentiment=("sentiment_score", "mean"),
        )
        .reset_index()
        .sort_values("date")
    )

    return dataframe_to_records(result)


@app.get("/stats/keywords")
def keyword_stats(limit: int = Query(default=20, ge=1, le=100)):
    """Return top keywords from cleaned post text."""
    df = load_posts()

    if df.empty:
        return []

    text_source = "clean_text" if "clean_text" in df.columns else "text"
    text = " ".join(df[text_source].dropna().astype(str).tolist()).lower()

    words = re.findall(r"\b[a-z]{3,}\b", text)

    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "are",
        "was", "were", "have", "has", "had", "you", "your", "but",
        "not", "about", "into", "over", "our", "their", "they", "them",
        "his", "her", "she", "him", "its", "who", "what", "when",
        "where", "why", "how", "can", "will", "would", "could",
        "should", "been", "being", "than", "then", "also", "just",
        "australia", "australian", "http", "https", "www", "com",
    }

    filtered_words = [word for word in words if word not in stopwords]
    counts = Counter(filtered_words).most_common(limit)

    return [{"keyword": word, "count": count} for word, count in counts]


@app.get("/stats/summary")
def summary_stats():
    """Compact summary of the social media dataset."""
    df = load_posts()

    if df.empty:
        return {
            "total_posts": 0,
            "platforms": [],
            "conflicts": [],
            "date_min": None,
            "date_max": None,
            "avg_sentiment": None,
        }

    valid_dates = df.dropna(subset=["date"])

    return {
        "total_posts": int(len(df)),
        "platforms": sorted(df["platform"].dropna().unique().tolist()),
        "conflicts": sorted(df["conflict"].dropna().unique().tolist()),
        "date_min": valid_dates["date"].min().strftime("%Y-%m-%d") if not valid_dates.empty else None,
        "date_max": valid_dates["date"].max().strftime("%Y-%m-%d") if not valid_dates.empty else None,
        "avg_sentiment": float(df["sentiment_score"].mean()) if df["sentiment_score"].notna().any() else None,
    }


@app.get("/market/prices")
def get_market_prices(
    limit: int = Query(default=100, ge=1, le=10000),
    benchmark: Optional[str] = None,
):
    """
    Return market price records from Elasticsearch.

    Examples:
    /market/prices?limit=20
    /market/prices?benchmark=Brent&limit=20
    """
    df = load_market_prices()

    if benchmark:
        df = df[df["benchmark"].astype(str).str.lower() == benchmark.lower()]

    df = df.sort_values("date", ascending=False)

    return dataframe_to_records(df.head(limit))


@app.get("/market/latest")
def latest_market_price(
    benchmark: str = Query(default="Brent"),
):
    """
    Return latest market price for a benchmark.

    Example:
    /market/latest?benchmark=Brent
    """
    df = load_market_prices()

    if df.empty:
        return None

    df = df[df["benchmark"].astype(str).str.lower() == benchmark.lower()]
    df = df.dropna(subset=["date", "price"])

    if df.empty:
        return None

    latest = df.sort_values("date", ascending=False).head(1)
    return dataframe_to_records(latest)[0]
