import os
import re
import warnings
from datetime import datetime, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup
from mastodon import Mastodon
from textblob import TextBlob
from elasticsearch import Elasticsearch, helpers

warnings.filterwarnings("ignore")

# ===== Credentials =====
# In local development these default to files in the project root.
# In Kubernetes CronJob, the mounted secret file paths are passed through env vars.
MASTODON_CLIENT_ID = os.getenv("MASTODON_CLIENTCRED_FILE", "mastodon_clientcred.secret")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_USERCRED_FILE", "mastodon_usercred.secret")
MASTODON_INSTANCE_URL = os.getenv("MASTODON_INSTANCE_URL", "https://mastodon.social")

BLUESKY_IDENTIFIER = os.getenv("BLUESKY_IDENTIFIER", "yaojinw.bsky.social")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD", "hv3j-mqmq-ruvq-y6s2")

# Official oil price data
EIA_SPOT_XLS_URL = "https://www.eia.gov/dnav/pet/xls/PET_PRI_SPT_S1_D.xls"

# Elasticsearch
ES_URL = os.getenv("ES_URL", "http://localhost:9200")
es = Elasticsearch(ES_URL)


def get_mastodon_data(limit, keywords, instance_url=MASTODON_INSTANCE_URL):
    mastodon = Mastodon(
        client_id=MASTODON_CLIENT_ID,
        access_token=MASTODON_ACCESS_TOKEN,
        api_base_url=instance_url,
    )

    data = []
    seen_ids = set()
    per_query_limit = max(limit // max(len(keywords), 1), 1)

    for q in keywords:
        max_id = None
        collected_for_query = 0

        while collected_for_query < per_query_limit and len(data) < limit:
            try:
                results = mastodon.search_v2(
                    q=q,
                    resolve=True,
                    result_type="statuses",
                    max_id=max_id,
                )

                new_statuses = results.get("statuses", []) if isinstance(results, dict) else []

                if not new_statuses:
                    break

                for toot in new_statuses:
                    toot_id = str(toot.get("id"))

                    if toot_id in seen_ids:
                        continue

                    seen_ids.add(toot_id)

                    soup = BeautifulSoup(toot.get("content", ""), "html.parser")
                    text_content = soup.get_text(" ", strip=True)

                    created_at = toot.get("created_at")
                    if hasattr(created_at, "strftime"):
                        date_str = created_at.strftime("%Y-%m-%d")
                    else:
                        date_str = str(created_at)[:10]

                    account = toot.get("account", {}) or {}

                    data.append({
                        "platform": "Mastodon",
                        "date": date_str,
                        "text": text_content,
                        "author": account.get("username", ""),
                        "upvotes": int(toot.get("favourites_count", 0)),
                        "url": toot.get("uri", ""),
                    })

                collected_for_query += len(new_statuses)
                max_id = new_statuses[-1].get("id")

                if len(data) >= limit:
                    break

            except Exception as e:
                print(f"Mastodon error ({q}): {e}")
                break

    return pd.DataFrame(data[:limit])


def get_bluesky_data(keywords, limit):
    if not BLUESKY_IDENTIFIER or not BLUESKY_PASSWORD:
        return pd.DataFrame(columns=["platform", "date", "text", "author", "upvotes", "url"])

    session_url = "https://bsky.social/xrpc/com.atproto.server.createSession"

    response = requests.post(
        session_url,
        json={
            "identifier": BLUESKY_IDENTIFIER,
            "password": BLUESKY_PASSWORD,
        },
        timeout=20,
    )

    if response.status_code != 200:
        print(f"BlueSky login failed: {response.status_code}")
        return pd.DataFrame(columns=["platform", "date", "text", "author", "upvotes", "url"])

    access_token = response.json()["accessJwt"]
    headers = {"Authorization": f"Bearer {access_token}"}
    base_url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"

    data = []
    queries = [{"q": k, "cursor": None, "count": 0} for k in keywords]
    per_query_limit = max(limit // max(len(queries), 1), 1)

    for query in queries:
        while query["count"] < per_query_limit and len(data) < limit:
            params = {
                "q": query["q"],
                "limit": 100,
                "cursor": query["cursor"],
            }

            try:
                resp = requests.get(base_url, headers=headers, params=params, timeout=20)
                resp.raise_for_status()
                result = resp.json()

            except Exception as e:
                print(f"BlueSky error ({query['q']}): {e}")
                break

            posts = result.get("posts", [])
            if not posts:
                break

            for post in posts:
                record = post.get("record", {}) or {}
                author = post.get("author", {}) or {}
                uri = post.get("uri", "")
                did = author.get("did", "")
                rkey = uri.split("/")[-1] if uri else ""

                created_at = post.get("indexedAt", "")
                date_str = created_at[:10] if isinstance(created_at, str) else ""

                data.append({
                    "platform": "BlueSky",
                    "date": date_str,
                    "text": record.get("text", ""),
                    "author": author.get("handle", ""),
                    "upvotes": int(post.get("likeCount", 0)),
                    "url": f"https://bsky.app/profile/{did}/post/{rkey}" if did and rkey else "",
                })

                if len(data) >= limit:
                    break

            query["cursor"] = result.get("cursor")
            query["count"] += len(posts)

            if not query["cursor"] or len(data) >= limit:
                break

    return pd.DataFrame(data[:limit])


def load_eia_oil_prices():
    last_error = None

    for header in [0, 1, 2, 3, 4, 5, 6]:
        try:
            raw = pd.read_excel(EIA_SPOT_XLS_URL, sheet_name=1, header=header)
            raw.columns = [str(c).strip() for c in raw.columns]

            date_candidates = [
                c for c in raw.columns
                if re.search(r"date|period|month|day", str(c), re.I)
            ]

            date_col = date_candidates[0] if date_candidates else raw.columns[0]

            col_map = {}
            for c in raw.columns:
                cl = str(c).lower()
                if "brent" in cl:
                    col_map[c] = "Brent"
                elif "wti" in cl or "west texas" in cl:
                    col_map[c] = "WTI"

            if not col_map:
                continue

            keep_cols = [date_col] + list(col_map.keys())
            df = raw[keep_cols].copy()
            df = df.rename(columns=col_map)

            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])

            long_df = df.melt(
                id_vars=[date_col],
                var_name="benchmark",
                value_name="price",
            )

            long_df = long_df.rename(columns={date_col: "date"})
            long_df["price"] = pd.to_numeric(long_df["price"], errors="coerce")
            long_df = long_df.dropna(subset=["price"])
            long_df = long_df.sort_values("date").reset_index(drop=True)
            long_df = long_df[long_df["date"] >= "2022-01-01"].reset_index(drop=True)

            return long_df

        except Exception as e:
            last_error = e

    print(f"EIA error: {last_error}")
    return pd.DataFrame(columns=["date", "benchmark", "price"])


def analyze_sentiment(text):
    if pd.isna(text) or str(text).strip() == "":
        return 0.0

    return TextBlob(str(text)).sentiment.polarity


def categorize_conflict(text):
    text_lower = str(text).lower()

    if "ukraine" in text_lower or "russia" in text_lower or "putin" in text_lower:
        return "Ukraine War"

    elif "gaza" in text_lower or "israel" in text_lower or "palestine" in text_lower:
        return "Gaza Conflict"

    elif "iran" in text_lower:
        return "Iran Tensions"

    return "Other"


def clean_text_for_wordcloud(text):
    if pd.isna(text):
        return ""

    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def ingest_social_posts():
    print("Collecting real social media data...")

    conflict_keywords = [
        "Ukraine Australia",
        "Gaza conflict Australia",
        "Iran Australia",
    ]

    post_limit_per_platform = 100

    df_mastodon = get_mastodon_data(
        limit=post_limit_per_platform,
        keywords=[f"{k} Australia" for k in conflict_keywords],
    )

    df_bluesky = get_bluesky_data(
        keywords=[f"{k} Australia" for k in conflict_keywords],
        limit=post_limit_per_platform,
    )

    frames = [
        df for df in [df_mastodon, df_bluesky]
        if df is not None and not df.empty
    ]

    if not frames:
        print("No social media data collected.")
        return

    df_all = pd.concat(frames, ignore_index=True)

    df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")
    df_all = df_all.dropna(subset=["date"]).copy()
    df_all["date"] = df_all["date"].dt.strftime("%Y-%m-%d")

    df_all["text"] = df_all["text"].fillna("")
    df_all["sentiment_score"] = df_all["text"].apply(analyze_sentiment)
    df_all["conflict"] = df_all["text"].apply(categorize_conflict)
    df_all["clean_text"] = df_all["text"].apply(clean_text_for_wordcloud)

    df_all = df_all[df_all["conflict"] != "Other"].copy()
    df_all = df_all.drop_duplicates(subset=["platform", "date", "text"]).reset_index(drop=True)

    docs = [
        {
            "_index": "social_posts",
            "_source": {
                "platform": row["platform"],
                "date": row["date"],
                "text": row["text"],
                "author": row["author"],
                "upvotes": int(row["upvotes"]) if pd.notna(row["upvotes"]) else 0,
                "url": row["url"],
                "sentiment_score": float(row["sentiment_score"]),
                "conflict": row["conflict"],
                "clean_text": row["clean_text"],
            },
        }
        for _, row in df_all.iterrows()
    ]

    if docs:
        success, failed = helpers.bulk(es, docs)
        print(f"Inserted social posts: {success}")
    else:
        print("No valid social posts after filtering.")


def ingest_market_prices():
    print("Collecting official oil price data...")

    oil_df = load_eia_oil_prices()

    if oil_df.empty:
        print("No oil price data collected.")
        return

    oil_df["date"] = pd.to_datetime(oil_df["date"], errors="coerce")
    oil_df = oil_df.dropna(subset=["date"]).copy()
    oil_df["date"] = oil_df["date"].dt.strftime("%Y-%m-%d")

    docs = [
        {
            "_index": "market_prices",
            "_source": {
                "date": row["date"],
                "benchmark": row["benchmark"],
                "price": float(row["price"]),
            },
        }
        for _, row in oil_df.iterrows()
    ]

    success, failed = helpers.bulk(es, docs)
    print(f"Inserted market price records: {success}")


if __name__ == "__main__":
    ingest_social_posts()
    ingest_market_prices()
    print("Real data ingestion completed.")