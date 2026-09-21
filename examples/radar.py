"""Read market activity in one call. Run with ALPHAI_API_KEY set."""

from alphai import Client

with Client() as client:
    snapshot = client.radar.snapshot(window="24h", market="us_equity", limit=10)
    print("Snapshot:", snapshot.snapshot_id, "as of", snapshot.as_of)
    print("Freshness:", snapshot.freshness)
    for reading in snapshot.results:
        print(reading.ticker, reading.stories, reading.news_z, reading.sent.value)
        for evidence in reading.evidence:
            print(" ", evidence.title, evidence.url)
