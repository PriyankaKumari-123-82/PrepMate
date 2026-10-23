# PrepMate · Teacher Copilot

PrepMate turns textbook PDFs into page-grounded study material. Students can upload a chapter, practise generated questions, ask questions about the text, and track which concepts need more work.

The teacher workspace adds a multi-tenant educator copilot. Teachers can generate cited assessments, lesson plans, notes, slide outlines, worksheets, and course plans from uploaded PDFs. Every generation records explicit knowledge, specialist, and review steps; outputs remain drafts until submitted and approved by an HOD or institution admin.

Students also have a private **Career Prep** workspace. It parses resume evidence for review, compares confirmed skills with a target role or job description, and creates an explainable seven-day preparation plan with trackable tasks.

## Live deployment

- Frontend: [https://prepmate-web.priyankamsc24.workers.dev](https://prepmate-web.priyankamsc24.workers.dev)
- Backend: [https://prepmate-ix72.onrender.com](https://prepmate-ix72.onrender.com)
- API documentation: [https://prepmate-ix72.onrender.com/docs](https://prepmate-ix72.onrender.com/docs)

## Requirements

- Docker with Docker Compose (recommended)
- Node.js and npm only for frontend development
- An OpenAI-compatible API key is optional; local fallbacks keep the app usable without one

## Run the complete app with Docker

1. Create the environment file:

   ```bash
   cp .env.example .env
   ```

2. Optionally add `LLM_API_KEY=your-api-key` to `.env` for LLM-generated chat answers. Without a key, PrepMate uses deterministic local embeddings and extractive answers from the textbook.

3. Build and start PostgreSQL, the backend, and the frontend:

   ```bash
   docker compose up --build
   ```

4. Open:

   - Student app: http://localhost:5173
   - API documentation: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

Database migrations run automatically when the backend container starts. Stop with `Ctrl+C`, or use `docker compose down` if the app is detached.

To run in the background:

```bash
docker compose up --build -d
docker compose logs -f
```

### Port 5173 is already allocated

Find the container using the frontend port:

```bash
docker ps --filter publish=5173
```

Stop that container, or change the `web` port mapping in `docker-compose.yml` from `5173:80` to another host port such as `5174:80`.

## Run the frontend in development mode

Use this setup for React development with Vite hot reload.

1. Start only PostgreSQL and the backend:

   ```bash
   cp .env.example .env
   docker compose up --build db api
   ```

2. In another terminal, start Vite:

   ```bash
   cd web
   npm install
   npm run dev
   ```

3. Open http://localhost:5173.

Vite proxies `/api` requests to `http://localhost:8000`. Do not start the Compose `web` service at the same time because both frontends use port 5173.

Useful frontend commands:

```bash
cd web
npm run build     # type-check and create a production build
npm run preview   # preview the production build
```

## Backend development and tests

Run tests inside the backend image so they use the project dependencies:

```bash
docker compose run --rm api pytest -q
```

For a native Python environment, Python 3.11 or newer is required:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

The provided `.env.example` expects PostgreSQL at the Compose hostname `db`. To run the API directly on the host, first set `DATABASE_URL` to a host-accessible PostgreSQL/pgvector database, then run:

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

## How each feature works

### Account and sign-in

Create an account with an email address and a password of at least eight characters. Registration and login return a JWT. The frontend stores it in the browser and sends it with protected requests. Documents, attempts, and results are restricted to their owner.

### PDF library and ingestion

From **Library**, select **Upload chapter** and choose a PDF. The library refreshes every five seconds and displays these stages:

1. **Extracting** – PyMuPDF reads text one page at a time.
2. **Indexing** – page-bounded chunks and embeddings are stored in PostgreSQL.
3. **Generating** – grounded concepts and short-answer questions are created.
4. **Ready** – the chapter is available for practice and textbook chat.

Uploads are limited to PDFs of 30 MB and 250 pages. Scanned image-only PDFs are not OCRed yet and may not contain enough text for useful study material.

### Chapter and concept map

Open a ready chapter to see extracted concepts, summaries, and mastery scores. New concepts begin at 30%, and their scores change after practice answers. **Open PDF** displays the original uploaded document.

### Practice sessions

Select **Start practice** on a ready chapter. PrepMate creates up to ten questions, prioritising concepts with lower mastery while randomising equally ranked questions.

For each response, PrepMate:

- grades short answers using keyword overlap with the grounded answer;
- immediately displays the result and explanation;
- shows the exact source quote;
- links to the source PDF page; and
- updates the related concept's mastery.

The final question submits the session and updates the progress data.

### Ask your textbook

Open **Ask textbook**, choose a ready chapter, and enter a question. PrepMate searches only that document, combines semantic and keyword retrieval, and ranks relevant page chunks. The response includes citations that open the matching page in the PDF.

With `LLM_API_KEY`, the configured OpenAI-compatible model writes a grounded answer. Without a key, PrepMate returns relevant extracted textbook context.

### Progress dashboard

The **Progress** page shows overall accuracy, total answers, up to five weakest concepts, and the recommended topic to study next. The recommendation is the concept with the lowest current mastery.

## Configuration

| Variable | Purpose | Example/default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL/pgvector connection | Compose database |
| `JWT_SECRET` | Signs authentication tokens | Development placeholder |
| `LLM_API_KEY` | Enables remote embeddings and chat answers | Empty/local fallback |
| `LLM_BASE_URL` | OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `LLM_MODEL` | Chat model | `gpt-4o-mini` |
| `EMBED_MODEL` | Embedding model | `text-embedding-3-small` |
| `EMBEDDING_DIM` | Stored vector dimensions | `1536` |
| `UPLOAD_DIR` | PDF storage path | `/data/uploads` |
| `CORS_ORIGINS` | Allowed browser origins | `http://localhost:5173` |

Change `JWT_SECRET` before deployment.

## Free-tier deployment (Cloudflare Pages + Render + Supabase)

This split deployment keeps the React site static, runs FastAPI as a Docker web service, uses Supabase PostgreSQL with pgvector, and stores uploaded PDFs in a private Supabase Storage bucket. Free-tier quotas, sleeping, and availability can change; this setup is intended for a small demo, not production workloads.

1. Create a Supabase project. Enable the `vector` extension (the first Alembic migration also attempts to enable it), create a **private** Storage bucket named `prepmate-pdfs`, and set its upload limit to at least 30 MB. Use the project's database connection string in `DATABASE_URL`; the connection URL must use the `postgresql+psycopg://` SQLAlchemy driver form. URL-encode reserved characters in the password (for example, `@` as `%40`); the app also normalizes raw `@` characters for compatibility. Keep the service-role key private and use it only as a Render secret.
2. Deploy the backend to Render from this repository using the included `render.yaml` Blueprint. Set `DATABASE_URL`, `JWT_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `CORS_ORIGINS` in the Render service's environment. Set `CORS_ORIGINS` to the exact Cloudflare Pages origin after creating the site (for example, `https://your-site.pages.dev`). The blueprint selects Supabase Storage; local development continues to use the `local` backend.
3. Create a Cloudflare Pages project connected to the repository. Set the root directory to `web`, the build command to `npm run build`, and the output directory to `dist`. Add the build-time environment variable `VITE_API_URL` with the Render service origin, without a trailing slash or `/api` suffix (for example, `https://your-api.onrender.com`).
4. After the first Render deploy, verify `https://your-api.onrender.com/health`, then set the Pages origin in Render's `CORS_ORIGINS` and redeploy. Register a test account, upload a PDF, and verify that it appears in the private Supabase bucket and can be opened through the app.

`SUPABASE_SERVICE_ROLE_KEY` is a backend secret and must never be configured as a `VITE_*` variable or exposed to the browser. Free Render instances may sleep; the initial API request can be slow, and in-process PDF ingestion is not durable if an instance restarts. The free Supabase database/storage capacity is limited, so monitor its current dashboard quotas.

## Main API routes

- `POST /auth/register`, `POST /auth/login`
- `POST /documents`, `GET /documents`
- `GET /documents/{id}`, `/status`, `/file`, and `/concepts`
- `POST /tests`
- `POST /attempts/{id}/answers`, `POST /attempts/{id}/submit`
- `POST /questions/{id}/flag`
- `POST /chat`
- `GET /dashboard`
- `POST/GET /subjects`, `POST/GET /courses`, `POST /courses/{id}/units`, `POST /units/{id}/outcomes`
- `POST /artifacts/generate`, `GET/PATCH /artifacts/{id}`
- `POST /artifacts/{id}/review`, `/submit`, and `/approve`
- `GET /runs/{id}` for the persisted workflow trace

Open **Teacher studio** in the web app after uploading and indexing a PDF. New registrations receive an isolated institution tenant and admin membership; generated artifacts, courses, subjects, reviews, and approvals are tenant-scoped.

Interactive request and response details are available at http://localhost:8000/docs while the backend is running.

## Current limitations

- OCR for scanned PDFs is not implemented.
- Ingestion uses FastAPI background tasks rather than a durable worker queue.
- The offline question bank currently generates grounded short-answer questions; the data model also supports multiple choice.
- Local fallback embeddings are intended for development, not production-quality semantic search.
