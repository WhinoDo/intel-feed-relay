# intel-feed-relay

RSS/API feed relay for sources unreachable from the CN server (arXiv, Substack, The Robot Report, HuggingFace).
GitHub Actions fetches on schedule and commits snapshots under out/; the consumer reads them from raw.githubusercontent.com.

Files:
- out/arxiv-cs-ro.xml — arXiv cs.RO RSS
- out/import-ai.xml — Import AI (Substack) RSS
- out/robot-report.xml — The Robot Report RSS
- out/hf-daily-papers.json — HuggingFace daily papers API JSON
