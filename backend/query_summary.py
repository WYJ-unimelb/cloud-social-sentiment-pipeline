from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

# ===== 1. Total Number of Posts =====
res = es.count(index="social_posts")
print(f"Total social posts: {res['count']}")

# ===== 2. The quantity of each type of conflict =====
conflict_query = {
    "size": 0,
    "aggs": {
        "conflicts": {
            "terms": {
                "field": "conflict.keyword"
            }
        }
    }
}

res = es.search(index="social_posts", body=conflict_query)

print("\nPosts per conflict:")
for bucket in res["aggregations"]["conflicts"]["buckets"]:
    print(f"{bucket['key']}: {bucket['doc_count']}")

# ===== 3. average sentiment =====
sentiment_query = {
    "size": 0,
    "aggs": {
        "avg_sentiment": {
            "avg": {
                "field": "sentiment_score"
            }
        }
    }
}

res = es.search(index="social_posts", body=sentiment_query)

avg_sentiment = res["aggregations"]["avg_sentiment"]["value"]
print(f"\nAverage sentiment score: {avg_sentiment:.4f}")

# ===== 4. The latest oil price (Brent)=====
price_query = {
    "size": 1,
    "query": {
        "term": {
            "benchmark.keyword": "Brent"
        }
    },
    "sort": [
        {"date": {"order": "desc"}}
    ]
}

res = es.search(index="market_prices", body=price_query)

if res["hits"]["hits"]:
    latest = res["hits"]["hits"][0]["_source"]
    print("\nLatest Brent price:")
    print(f"Date: {latest['date']}, Price: {latest['price']}")
else:
    print("No price data found")