from elasticsearch import Elasticsearch, helpers

es = Elasticsearch("http://localhost:9200")

docs = []

for i in range(10):
    docs.append({
        "_index": "social_posts",
        "_source": {
            "platform": "Mastodon",
            "date": "2025-04-01",
            "text": f"post content {i}",
            "author": f"user_{i}",
            "upvotes": i,
            "url": f"https://example.com/post/{i}",
            "sentiment_score": -0.1 * i,
            "conflict": "Gaza Conflict",
            "clean_text": f"cleaned post content {i}"
        }
    })

success, failed = helpers.bulk(es, docs)

print(f"Bulk insert success: {success}")
print(f"Bulk insert failed: {failed}")