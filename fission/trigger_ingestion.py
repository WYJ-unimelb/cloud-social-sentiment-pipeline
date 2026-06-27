import urllib.request


def main():
    """
    Fission timer function.

    This function invokes the internal FastAPI ingestion endpoint inside
    the Kubernetes cluster:

    Fission Timer -> Fission Function -> FastAPI /ingest/run -> Elasticsearch
    """
    url = "http://comp90024-api.comp90024.svc.cluster.local:8000/ingest/run"
    request = urllib.request.Request(url, method="POST")

    with urllib.request.urlopen(request, timeout=900) as response:
        return response.read().decode("utf-8")
