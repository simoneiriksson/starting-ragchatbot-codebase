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
