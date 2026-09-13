🧠 Core Optimization Phase (Legacy Script Fix)
Note: Before migrating to Airflow, the initial phase of this project involved strictly optimizing the legacy Python ETL script to handle OOM errors and fix data duplication (idempotency issues).

You can review the raw, highly optimized Python implementation (featuring generator-based memory limits, exact Postgres COPY ingestion, and a detailed POSTMORTEM document) in my initial development repository here:
[https://github.com/Illia263/intenship/tree/task-3/fix-the-pipeline/fix-the-pipeline]
