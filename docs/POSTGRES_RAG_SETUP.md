# PostgreSQL embeddings and the three-agent report flow

The active FastAPI app now generates 384-dimensional MiniLM embeddings and stores them in your application's database. In production, `DATABASE_URL` must point to PostgreSQL. The `vector` extension supplies the `vector(384)` column and cosine similarity search.

## Where the data is stored

| Table | Contents |
| --- | --- |
| `datasets` | Original uploaded rows, column mapping, and owner |
| `embedding_indexes` | Dataset owner, embedding model, content fingerprint, and indexed row count |
| `record_embeddings` | Record text, metadata, filter fields, and the actual `embedding vector(384)` |
| `reports` | Generated report, calculated KPIs, and charts |
| `report_evidence` | A saved copy of the records retrieved for that report, including source IDs and similarity scores |

On Render these tables use the **same PostgreSQL database identified by `DATABASE_URL`**. Dataset embeddings do not depend on the web service's filesystem. The Docker image caches only the embedding model's weights.

## How the flow works

1. An uploaded CSV/JSON file is validated and mapped to sales or marketing fields.
2. Each standardized row becomes a short text document. A `description` column, when present, is included.
3. MiniLM creates a real semantic embedding for each document, in CPU batches.
4. Documents and embeddings are committed together to PostgreSQL. Repeated requests reuse an unchanged index.
5. A report question/focus is embedded with the same model. PostgreSQL retrieves the closest records within the selected dataset and its business filters.
6. The Analyst receives the retrieved record text and source IDs alongside the exact KPI/aggregation snapshot.
7. The Writer receives the same original evidence and the Analyst's findings.
8. The Critic receives the same original evidence and the draft. A rejected draft goes back to the Writer, followed by another Critic review.
9. The report and the retrieved evidence are saved. Source records appear in the report and its JSON export.

The agents receive the **retrieved text**, not arrays of embedding numbers. Retrieved rows are examples; totals and rankings still come from the complete filtered dataset. All three agents are instructed to treat source text as data, never instructions.

## Update an existing Render deployment

1. Copy this project's contents into your existing repository and push the changes to GitHub.
2. Keep the existing Render PostgreSQL database and its `DATABASE_URL`. Use its Internal Database URL when the web service and database share a Render region.
3. Keep/set these environment values on the web service:

   ```dotenv
   ENVIRONMENT=production
   DATABASE_URL=<your existing Render PostgreSQL connection string>
   JWT_SECRET=<your existing strong secret>
   GROQ_API_KEY=<your Groq API key>
   GROQ_MODEL=llama-3.3-70b-versatile
   EMBEDDING_CACHE_DIR=/app/.cache/fastembed
   EMBEDDING_LOCAL_FILES_ONLY=true
   EMBEDDING_THREADS=1
   EMBEDDING_BATCH_SIZE=16
   RAG_TOP_K=6
   ```

4. Deploy the latest commit using the supplied **Dockerfile**. It builds the frontend, installs the API dependencies, downloads/tests MiniLM during the build, and runs one Uvicorn worker. Model downloads are disabled at runtime for this image.
5. On startup, the app runs `CREATE EXTENSION IF NOT EXISTS vector` and creates the three new tables. Existing users, datasets, and reports are retained. Do not delete/recreate your existing database.
6. Existing uploads and bundled demo records are indexed automatically on their first report request. New ready-to-use uploads are indexed after upload. Initial indexing takes longer than subsequent retrievals.

For a new deployment, use the included `render.yaml` Blueprint, supplying `GROQ_API_KEY` when prompted. It connects the web service to PostgreSQL automatically. Deploying a new Blueprint is not required for updating an existing service.

Render supports pgvector; the extension's SQL name is **`vector`**. If the database role cannot create extensions, enable it once using an authorized database owner before starting the app. Startup fails clearly if production points at SQLite or pgvector cannot be enabled.

## Verify after deploying

1. Sign in and upload a small CSV. The dataset card should say **Semantic search ready**. Older datasets can be indexed by generating a report or choosing **Retry source indexing**.
2. Open `/api/system/status` in the signed-in browser. Check:

   ```json
   {
     "autogen_enabled": true,
     "embedding_store": "postgresql+pgvector",
     "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
     "embedding_dimensions": 384,
     "rag_enabled": true
   }
   ```

3. Generate a report. The returned report should include `retrieval.status: "ready"`, `retrieval.records`, and an AutoGen provider value when the Groq calls succeed. The report includes a Retrieved source records section.
4. In the Render database's SQL session, verify storage:

   ```sql
   SELECT extversion FROM pg_extension WHERE extname = 'vector';

   SELECT scope, dataset_id, model, record_count
   FROM embedding_indexes;

   SELECT index_scope, record_key, vector_dims(embedding) AS dimensions
   FROM record_embeddings
   LIMIT 10;

   SELECT count(*) AS stored_embeddings FROM record_embeddings;
   ```

   After indexing a two-row dataset, its index should have two embedding rows, each with 384 dimensions. A demo-data index contains 2,000 rows. Indexes are created on demand, so a fresh deployment can have zero embeddings before an upload/report.

## Failures, updates, and privacy

- Retrieval is restricted to the authenticated account and selected dataset. Bundled demo records have their own shared scope and never mix in private uploads.
- The retrieval filters follow the same rules as dashboard analytics, including product/channel/region/quarter filters.
- Mapping changes invalidate and rebuild that dataset's index. Deleting a dataset removes its index and vectors. Previously generated reports retain the evidence they used.
- If embedding generation fails, the uploaded dataset remains saved and its status shows indexing pending. Retry with `POST /api/datasets/{id}/embeddings/reindex`, or generate a report to retry automatically.
- A report returns a controlled 503 if retrieval cannot be prepared; it does not claim to have used unavailable evidence.
- A missing Groq key, a Groq outage/rate limit, or a draft still rejected after revision uses the existing deterministic report fallback. Its provider label identifies the fallback. **Set a working `GROQ_API_KEY` to run the three AI agents.**
- No embedding API key is needed. MiniLM runs inside the web service. The source text retrieved for AI reports is sent to Groq through the existing AutoGen integration.
- This uses exact pgvector cosine search after filtering. It is intended for the existing upload limit of 10,000 rows per dataset; no approximate vector index is required.

## Local development and tests

Copy `.env.example` to `.env`, install `requirements-dev.txt`, then start `uvicorn app:app --reload --port 8000`. The backend loads `.env` without overriding existing environment variables. Local SQLite stores the same vectors as JSON and computes cosine similarity in Python. Production requires PostgreSQL.

For local PostgreSQL, use a database with pgvector installed and set `DATABASE_URL`. The application creates the extension/tables at startup.

```bash
python -m pytest -q
```

The standard suite uses deterministic test embeddings. Enable the real MiniLM integration test with `RUN_REAL_EMBEDDINGS=1`; its first run downloads the model unless it is already cached. Tests never use your real Groq key.

To run the suite against PostgreSQL, set `TEST_DATABASE_URL` to a **dedicated test database whose name ends in `_test`**. Tests create and drop application tables in that database. The included GitHub Actions job starts `pgvector/pgvector:pg16` and runs the suite with real MiniLM testing enabled.

The legacy top-level `vector_db.py`/`rag_retrieval.py` scripts remain separate historical entry points. Run the active app through `uvicorn app:app` to use this PostgreSQL pipeline.

## References

- [Render PostgreSQL extensions](https://render.com/docs/postgresql-extensions)
- [pgvector Python / SQLAlchemy integration](https://github.com/pgvector/pgvector-python#sqlalchemy)
- [FastEmbed](https://github.com/qdrant/fastembed)
