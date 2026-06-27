from elasticsearch import Elasticsearch

# connect ES
es = Elasticsearch("http://localhost:9200")

# ===== 1. social post data =====
social_doc = {
    "platform": "Mastodon",
    "date": "2025-04-01",
    "text": "post content here",
    "author": "username",
    "upvotes": 12,
    "url": "https://example.com",
    "sentiment_score": -0.25,
    "conflict": "Gaza Conflict",
    "clean_text": "cleaned post content"
}

# write into ES
res1 = es.index(index="social_posts", document=social_doc)
print("Inserted social post:", res1)

# ===== 2. market price data =====
market_doc = {
    "date": "2025-04-01",
    "benchmark": "Brent",
    "price": 87.3
}

res2 = es.index(index="market_prices", document=market_doc)
print("Inserted market price:", res2)

# ===== validation =====
result = es.search(index="social_posts")
print("\nSearch result:")
for hit in result["hits"]["hits"]:
    print(hit["_source"])