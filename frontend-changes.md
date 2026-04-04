# Frontend Changes

## Code Quality Tooling: Prettier

### What was added

- `frontend/package.json` — Node package manifest declaring Prettier as a dev dependency and exposing two npm scripts
- `frontend/.prettierrc` — Prettier formatting configuration tuned to match the existing code style
- `frontend/.prettierignore` — Excludes `node_modules/` from formatting
- `.gitignore` — Added `frontend/node_modules/` entry
- Prettier applied to `frontend/index.html`, `frontend/style.css`, `frontend/script.js`

### How to use

```bash
cd frontend
npm install          # one-time setup (installs Prettier locally)

npm run format       # format all HTML/CSS/JS files in-place
npm run format:check # check formatting without making changes (exit 1 if any file differs — useful in CI)
```

### Configuration decisions (`frontend/.prettierrc`)

| Option | Value | Reason |
|---|---|---|
| `tabWidth` | `4` | Existing code uses 4-space indentation throughout |
| `useTabs` | `false` | Existing code uses spaces |
| `semi` | `true` | `script.js` uses semicolons on every statement |
| `singleQuote` | `true` | JS strings use single quotes; HTML attributes always use double quotes regardless of this setting |
| `printWidth` | `120` | Current longest lines reach ~197 chars (SVG polygon data) and ~190 chars (template literals); 80 would reformat data values with no readability benefit |
| `htmlWhitespaceSensitivity` | `"ignore"` | Treats all HTML elements as block-level, matching the hand-written indentation style |
| `trailingComma` | `"es5"` | Modern JS convention; Prettier v3 default |
| `endOfLine` | `"lf"` | Standard for macOS/Linux; prevents CRLF noise |

### Files formatted

All three frontend source files were passed through `npm run format` as part of this change to establish a clean formatting baseline.

---

## API Endpoint Testing Infrastructure

No frontend files were modified in this change.

This implementation added API endpoint testing infrastructure to the backend test suite:

### Files Changed

### `pyproject.toml`
- Added `httpx>=0.27.0` to `[dependency-groups] dev` (required by FastAPI's TestClient)
- Added `[tool.pytest.ini_options]` section:
  - `testpaths = ["backend/tests"]` — pytest discovers tests in the right directory
  - `pythonpath = ["backend"]` — makes backend modules importable without `sys.path` hacks in each file
  - `addopts = "-v"` — verbose output by default

### `backend/tests/conftest.py`
Added imports and three new fixtures above the existing shared data fixtures:
- **`_build_test_app(mock_rag)`** — builds a minimal FastAPI app with `/api/query` and `/api/courses` routes but *without* the static file mount (which requires `frontend/` to exist). This isolates tests from the filesystem.
- **`mock_rag`** fixture — a `MagicMock` pre-configured with sensible defaults that mirrors the `RAGSystem` interface used by the API layer.
- **`api_client`** fixture — a `fastapi.testclient.TestClient` wired to the test app; can be injected into any test that needs HTTP-level testing.

### `backend/tests/test_api.py` (new file)
18 tests across two classes:

**`TestQueryEndpoint`** — covers `POST /api/query`:
- Happy-path status code and response shape
- `session_id` auto-creation when omitted
- Provided `session_id` is passed through unchanged and `create_session` is not called
- Query string is forwarded to `RAGSystem.query()`
- Sources with and without URLs serialise correctly
- Missing `query` field returns HTTP 422
- RAGSystem exception propagates as HTTP 500

**`TestCoursesEndpoint`** — covers `GET /api/courses`:
- Happy-path status code and response shape
- Analytics values from the RAG system are returned verbatim
- Empty catalog (`total_courses=0`) serialises correctly
- RAGSystem exception propagates as HTTP 500

---

## Light/Dark Mode Toggle Button

### Files Modified
- `frontend/index.html` — added toggle button markup, bumped CSS/JS cache-bust version
- `frontend/style.css` — added light theme variables, toggle button styles, icon animation, theme transition
- `frontend/script.js` — added theme initialisation (reads localStorage on load) and toggle handler

### What Was Added

#### HTML (`index.html`)
A `<button id="themeToggle" class="theme-toggle">` is placed directly inside `<body>`, fixed-positioned in the top-right corner. It contains two inline SVGs:
- `.icon-sun` — shown in dark mode (default)
- `.icon-moon` — shown in light mode

Both icons carry `aria-hidden="true"`. The button has a dynamic `aria-label` ("Switch to light/dark mode") and a `title` tooltip for keyboard and screen-reader accessibility.

#### CSS (`style.css`)
- **Light theme variables** — a `[data-theme="light"]` ruleset (applied to `<html>`) overrides every colour token defined in `:root`:

  | Token | Light value | Notes |
  |---|---|---|
  | `--background` | `#f8fafc` | Page background |
  | `--surface` | `#ffffff` | Sidebar / cards |
  | `--surface-hover` | `#e2e8f0` | Hover states |
  | `--text-primary` | `#0f172a` | High-contrast body text (WCAG AA ✓) |
  | `--text-secondary` | `#64748b` | Muted / secondary text |
  | `--border-color` | `#e2e8f0` | Dividers and outlines |
  | `--primary-color` | `#2563eb` | Buttons, links, accents |
  | `--primary-hover` | `#1d4ed8` | Primary hover |
  | `--focus-ring` | `rgba(37,99,235,0.2)` | Keyboard focus indicator |
  | `--user-message` | `#2563eb` | User chat bubble |
  | `--assistant-message` | `#f1f5f9` | Assistant chat bubble |
  | `--shadow` | `rgba(0,0,0,0.1)` | Lighter drop-shadow |
  | `--welcome-bg/border` | `#eff6ff` / `#bfdbfe` | Welcome message highlight |
  | `--theme-toggle-*` | white / `#f1f5f9` / `#e2e8f0` | Toggle button surface colours |

  Scoped overrides are also added for code blocks (`rgba(0,0,0,0.07)` background), assistant message bubbles, and the welcome message card so they use the correct light-mode surfaces instead of the dark defaults.

  Four previously hardcoded colors were converted to CSS variables so they adapt correctly in both themes:

  | Variable | Dark value | Light value | Used on |
  |---|---|---|---|
  | `--source-link-color` | `#93c5fd` | `#1d4ed8` | Source pill link text |
  | `--source-link-hover` | `#bfdbfe` | `#1e40af` | Source pill link hover text |
  | `--error-color` | `#f87171` | `#dc2626` | `.error-message` text |
  | `--success-color` | `#4ade80` | `#16a34a` | `.success-message` text |
- **`.theme-toggle` button** — fixed 40 × 40 px circle, top-right (`top: 1rem; right: 1rem; z-index: 100`). Transitions on background, border, colour, and transform.
- **Icon animation** — `.icon-sun` and `.icon-moon` are absolutely-positioned and cross-fade with a rotate+scale transition (0.25 s opacity, 0.35 s transform). In dark mode the sun is visible; in light mode the moon is visible.
- **Global theme transitions** — `background-color`, `border-color`, and `color` transitions (0.25 s ease) applied to key structural elements for a smooth theme switch.

#### JS (`script.js`)
- **IIFE on load** (`script.js:5–9`) — reads `localStorage.getItem('theme')` and sets `data-theme="light"` on `<html>` before the DOM is fully parsed, preventing a flash of the wrong theme on reload.
- **`setupThemeToggle()`** (`script.js:58–76`) — attaches a click listener to `#themeToggle`. On each click it:
  1. Reads the current theme from `document.documentElement.getAttribute('data-theme')`
  2. Removes or sets `data-theme="light"` to switch themes
  3. Persists the new preference to `localStorage` so it survives page reloads
  4. Updates `aria-label` to reflect the action the button will perform next
- **Smooth transitions** — all colour changes animate via CSS `transition: background-color 0.25s ease, border-color 0.25s ease, color 0.25s ease` applied to the body, sidebar, chat container, messages, input, and buttons. No JS animation is needed; the browser handles it entirely through CSS.
