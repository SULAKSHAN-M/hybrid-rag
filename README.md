# SourceDesk Private Workspaces v2

A local document assistant with private accounts, saved conversations, hybrid retrieval and five-model automatic Gemini routing. Upload documents into collections, ask questions, inspect highlighted source passages, and export conversations with citations.

## What is included

| Feature | Implementation |
| --- | --- |
| Saved chats and follow-ups | SQLite conversation history; up to four recent turns provide context, and referential follow-ups expand the retrieval query with recent user questions. |
| Clickable citations | Authenticated page previews highlight the retrieved passage using original word coordinates. Text/Word files have text previews. |
| Collections | Each user has collections; a chat keeps its chosen search scope. Start a new chat to change scope. |
| OCR | Local Tesseract for low-text PDF pages and PNG/JPEG/TIFF/BMP images. |
| Unsupported answers | A configurable relevance threshold blocks generation on weak evidence; the model is prompted to abstain, and fabricated citation IDs/quotes are rejected. |
| Upload progress | Styled drag-and-drop upload area, filename/size preview, remove control and real browser transfer progress followed by polled extraction, OCR, chunking, model loading, embedding and indexing stages. Stage percentages are approximate. |
| Feedback | Helpful or incorrect/irrelevant feedback with a note is saved per answer. |
| Exports | Word and PDF downloads include questions, answers, supporting quotations and source names/page or section numbers. |
| Usage | Question count, response latency, selected model, fallback attempts, reported tokens and feedback totals. |
| Private workspaces | Local usernames/passwords, hashed passwords, expiring sessions, and owner checks across search, files, previews, jobs, chats, exports and feedback. |

## Upgrade your existing Windows installation

1. Stop SourceDesk with **Ctrl+C**.
2. Extract the new ZIP separately. Copy the new `app`, `tests`, `requirements.txt`, `README.md`, `Dockerfile`, `compose.yaml` and `.env.example` into your existing `hybrid-rag` directory, replacing the corresponding files.
3. Keep your existing `.venv`, `.env`, and `data` intact.
4. In PowerShell inside `C:\Users\ASUS\Desktop\hybrid-rag`, install the added packages:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

5. Keep your Gemini API key in `.env`:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_actual_key_here
```

6. Start the updated app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

7. Open http://localhost:8000 and press **Ctrl+F5**. Create a local account, then upload documents into your General collection.

**Existing shared documents need to be re-uploaded after signing in.** The old `data/chroma` index is retained untouched but is not queried by private workspaces. It has no ownership records, so the app does not assign it to the first account. The new private index uses `data/private-vectors`, metadata uses `data/workspace.sqlite3`, and original files use `data/files`.

## Fresh Windows setup

Python 3.10, 3.11 or 3.12 can be used. With Python 3.10 already installed:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Enter your Gemini key, save the file, and run the start command above. Get a key from https://aistudio.google.com/apikey. No key is included in this project. Without a key, document retrieval and saved chats still work, but generated answers do not.

First indexing downloads the embedding and cross-encoder models from Hugging Face and can take several minutes. Those models run locally on CPU afterward. Internet access is required for the initial models and Gemini requests.

## OCR setup on Windows

Install Tesseract OCR using the Windows installer linked from the Tesseract project's installation page:
https://tesseract-ocr.github.io/tessdoc/Installation.html

Add its actual executable path to `.env`, for example:

```dotenv
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
OCR_LANG=eng
```

Restart SourceDesk. The **Read scanned pages with OCR** checkbox enables recognition of low-text pages and images. Text PDFs do not need Tesseract. For Tamil/Sinhala or other languages, install their Tesseract language data and set `OCR_LANG` to the corresponding language codes, optionally combined with `+`. OCR quality depends on the scan and language data. Low-text pages are detected heuristically; mixed text/image pages with enough existing text are not fully OCRed. Multi-frame image uploads currently process the first frame.

## Docker

Docker includes Tesseract with English language data and a font for PDF exports:

```bash
cp .env.example .env
# Add your Gemini key to .env
docker compose up --build
```

On Windows use `Copy-Item .env.example .env` instead of `cp` if needed. If migrating an existing Windows `.env`, remove its Windows-specific `TESSERACT_CMD` before running Linux Docker. Open http://localhost:8000. Use one API worker. Named volumes retain metadata, originals, vectors and model downloads. Native and Docker installations use separate data stores by default.

## Using the workspace

- Create an account with a unique username and a password of at least 10 characters. Sign in afterward to access the same workspace.
- Select or create a collection, then upload a document. Select **All collections** for cross-collection searches, but select a specific collection when uploading.
- Ask a question. Follow-ups such as “Explain that further” reuse recent context. New topics may be clearer in a new chat.
- Click a source citation to view the highlighted source passage and extracted text. PDF page numbers are retained; non-PDF locators are sections rather than Word page numbers.
- Open saved conversations from the dropdown. Use **Rename** to set a name of up to 80 characters; the name is saved and will not be overwritten by later questions. Download Word/PDF exports using the links above the conversation.
- Submit feedback below an answer. The Usage dialog shows metrics for your own workspace.
- Remove documents from the sidebar. Saved chats retain previously quoted content; their original page previews become unavailable. Delete those chats separately when you also want the quoted history removed. Usage aggregates remain after deleting a chat.

## Five-model automatic routing

There is no model selector. The default pool is:

| First matching question rule | Preferred model |
| --- | --- |
| Analysis/comparison keywords or over 90 words | `gemini-3.1-pro-preview` |
| Coding/debugging keywords | `gemini-3.7-flash` |
| Over 18,000 context characters or 45 question words | `gemini-3.8-flash` |
| Summary/explanation keywords | `gemini-3.6-flash` |
| Short factual question | `gemini-3.5-flash-lite` |
| Other questions | `gemini-3.8-flash` |

This is a deterministic heuristic, not a guarantee of the best model. Keywords are English; other languages use length/context rules. Optional `GEMINI_ROUTER_MODELS` restricts the allowed pool. Legacy `GEMINI_MODEL` and `GEMINI_MODELS` settings are ignored.

Unavailable models (404), temporary server errors and connection failures can trigger fallbacks. At most five sequential attempts are scheduled within a 90-second budget, with up to 30 seconds per network call; elapsed time can be longer because network reads are not a hard wall-clock deadline. Quota, denied access, invalid requests, safety blocks and malformed responses stop without rotating models. Successful abstention stops as well. Failed or timed-out calls may still incur provider charges.

OpenAI compatibility is retained with `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL`; it uses one configured model.

## Evidence and usage limits

Hybrid retrieval uses local MiniLM embeddings, ChromaDB vectors, BM25, reciprocal rank fusion and cross-encoder reranking. The default `MIN_RERANK_SCORE=0` threshold uses raw cross-encoder logits and should be tuned against labelled questions from your own documents. It is not a confidence percentage or a calibrated guarantee. Follow-up resolution uses recent context heuristics, not a dedicated coreference model.

Generation uses only passages above the evidence threshold. Citation validation checks source IDs and verbatim quotation presence, not semantic entailment. A claim can still misinterpret a real quote. Review source passages for important decisions.

Token totals use provider-reported usage from successful responses only. Missing usage is shown as unreported; it is never estimated as zero in per-model totals. Failed/fallback requests may cost money without reporting usage, so this dashboard is not a billing statement. Document deletion does not erase historical exported files or downloaded copies.

## Privacy and deployment scope

Each account owns a private workspace in the application. Passwords use scrypt with per-user salts; session tokens are stored as hashes and delivered in HttpOnly SameSite cookies. Mutations require a custom same-origin request header. Login/registration attempts are throttled per direct client IP. Every private resource is owner scoped, including previews and exports.

The server administrator can access files, SQLite data and the shared provider key. Storage is not encrypted by this app. A single server API key is used for all users, so all usage is billed to that key. With AI enabled, the current question, recent conversation context and retrieved passages are sent to that provider. Embeddings/OCR remain local.

Default access is loopback-only. For a network deployment, configure HTTPS, `COOKIE_SECURE=true`, an exact `APP_ORIGIN`, appropriate proxy handling, backups, resource quotas and operational monitoring. Set `ALLOW_REGISTRATION=false` after creating desired accounts if open registration is not wanted. There is no email verification, password recovery, MFA, account deletion UI, team sharing, malware scanning or enterprise SSO. This is a functional local/portfolio application, not an independently audited enterprise service.

Ingestion uses an in-process worker pool. Interrupted jobs are marked failed on restart; remove and re-upload them. There is no durable distributed job queue. One answer is generated at a time across the server to prevent conversation write races. BM25 scans a workspace's selected corpus, so this implementation targets smaller collections.

Limits: 10 MB uploads, 250-page PDFs, 300,000 PDF words, 2 million text/DOCX characters, 20-megapixel uploaded images, 3 pending uploads per user. Scanned PDF pages have rendering-size checks. User storage is not subject to a total byte quota. Coordinate highlights cover retrieved chunks, which may be broader than a quotation. OCR highlights show recognized word positions and may be imperfect.

For non-Latin PDF exports, set `EXPORT_FONT` to a compatible TrueType font. Rendering and shaping depend on the chosen font and PDF library; Word exports are preferable if a script is not rendered correctly.

## API and tests

`/docs` provides the endpoint schema. Authentication uses the session cookie; include `X-Requested-With: SourceDesk` on mutations. Main routes cover accounts, collections, documents/jobs, chats/turns, sources/previews, exports, feedback and usage. The ask request is now `{"chat_id":"...","question":"..."}`.

```bash
python -m unittest discover -s tests -v
```

Validation for this release: core ranking/citation tests, mocked provider and routing tests, and FastAPI workflows for authentication, cross-user isolation, collection filtering, uploads, follow-ups, evidence refusal, feedback, usage, PDF previews and Word/PDF export. Workspace integration tests replace neural retrieval with a deterministic test double; provider calls are mocked. Real Tesseract image and scanned-PDF extraction and highlight generation were checked separately. Full neural model downloads/inference, paid provider calls, Docker build and Windows installation have not been executed in this build environment. Browser rendering was not verified: the Chromium download failed in this environment. Sample Word/PDF exports were rendered and visually inspected.

References:
- https://docs.trychroma.com/reference/python
- https://www.sbert.net/docs/cross_encoder/usage/usage.html
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- https://pymupdf.readthedocs.io/en/latest/page.html
- https://tesseract-ocr.github.io/tessdoc/Installation.html

## Upload interface cache fix

The static CSS and JavaScript now have content-versioned filenames, and the server revalidates static assets. Replace the full `app` folder when updating (not just `index.html`), restart the server and press Ctrl+F5. Keep `.env`, `.venv`, and `data` unchanged. If the browser shows an oversized folder icon or a native Choose File button inside the drop zone, verify that every file in `app/static` was copied.

### Conversation controls

Press **Enter** to send a question. Use **Shift + Enter** for a new line. On smaller screens, use **Library** to show or hide documents and collections. Completed upload progress clears after three seconds.

### Brand font

The SourceDesk wordmark requests locally installed Nexa Pro Bold/Regular. The font is not bundled. Browsers without Nexa Pro use Trebuchet MS or Arial. To use Nexa Pro for every visitor, supply licensed webfont files and change the local font sources to self-hosted URLs.

### Projects and conversation navigation

Uploads appear in the center of the workspace. Use Recents to reopen chats and the search icon to filter conversation names. The sidebar icon opens or closes project navigation. Existing collections appear as projects; use the star beside a project to pin or unpin it. Pins are saved per account in SQLite. This update requires replacing the full `app` folder and restarting the server; the project pin column is added automatically without removing data.
