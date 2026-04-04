# Frontend Changes

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
