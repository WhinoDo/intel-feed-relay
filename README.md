# intel-feed-relay

RSS/API feed relay for sources unreachable from the CN server (arXiv, Substack, The Robot Report, HuggingFace).
GitHub Actions fetches on schedule and commits snapshots under out/; the consumer reads them from raw.githubusercontent.com.

Files:
- out/arxiv-cs-ro.xml — arXiv cs.RO RSS
- out/import-ai.xml — Import AI (Substack) RSS
- out/robot-report.xml — The Robot Report RSS
- out/hf-daily-papers.json — HuggingFace daily papers API JSON

Import AI tries its live Substack RSS, the author's official jack-clark.net RSS,
and Substack's archive API, then RSSHub and morss on failure. Official article
links are preserved, so older and newer snapshots can use different domains.
Consumers switching between these feeds should deduplicate by newsletter issue;
the station has already migrated to the author's feed with historical deduplication.
Each candidate must be a nonempty RSS feed with article dates at least as recent
as the saved snapshot before it replaces that snapshot. If all candidates fail,
the previous snapshot stays available. The workflow processes and commits other
feeds, then reports failure so a stale Import AI snapshot cannot appear healthy.
Responses larger than 8 MiB are rejected without replacing the saved feed. Archived
Wayback responses are not treated as live updates. Run the offline regression
checks with `python3 -m unittest discover -s tests`.
