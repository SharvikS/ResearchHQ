# Comprehensive Code & UI/UX Audit: ResearchHQ Studio

This document contains a structured breakdown of the architectural flaws, code anti-patterns, and UI/UX issues identified in the `researchhq` (formerly `competiq`) project. 

**Target Audience:** Claude Code / AI Coding Assistants to execute step-by-step refactoring.

---

## 1. Code Architecture & Performance Flaws

### 1.1 UI Thread Blocking (Critical Performance Issue)
- **Synchronous DB/IO Calls:** Methods like `histdb.list_runs`, `histdb.aggregate`, and `histdb.reindex_from_folder()` are executed directly on the PySide6 main event loop (e.g., inside `dashboard.py` and `history_page.py`).
- **Aggressive Refresh Polling:** In `main_window.py` (Line 83), a `QTimer` hits `_dashboard.refresh()` every 3,000 milliseconds. This forces the UI thread to repeatedly query SQLite and read disk states, leading to UI jank, UI freezes as the dataset grows, and excessive CPU/battery drain.
- **Actionable Fix:** Move all `histdb` and IO operations into a separate `QThread` or `QRunnable` using `QThreadPool`. Use signals (`pyqtSignal`) to pass the data back to the main thread for UI rendering. Remove the 3-second polling timer and rely strictly on event-driven updates (e.g., refresh only when a run finishes or a file watcher detects changes).

### 1.2 Dangerous Exception Handling Anti-Patterns
- **Swallowing Exceptions:** The codebase pervasively uses `except Exception:  # noqa: BLE001` to suppress errors silently (e.g., `main_window.py:97`, `dashboard.py:138, 146`, `research_page.py:288, 413`, `history.py:99, 260, 267`).
- **Impact:** Network timeouts, missing schema columns, or malformed JSON reports will fail silently, leaving the user with an empty screen and no context in the logs.
- **Actionable Fix:** Replace bare `except Exception:` blocks with targeted exception handling (`sqlite3.Error`, `json.JSONDecodeError`, `IOError`). Any necessary broad catches must log the error (e.g., `logger.exception("...")`) rather than using `pass`.

### 1.3 State Coupling and Component Encapsulation
- **Tight Coupling:** Components access private methods of other widgets directly (e.g., `self._research._on_cancel()` inside `main_window.py`'s `closeEvent`). 
- **Actionable Fix:** Use PySide6 Signals and Slots for cross-component communication. The `MainWindow` should emit an `about_to_close` signal that `ResearchPage` connects to for graceful worker shutdown.

---

## 2. UI/UX Flaws & Missing Content

### 2.1 Missing Interactions & Stubbed Features
- **Disabled Pause/Resume:** The `Pause` button in the `ResearchPage` (`research_page.py:140`) is permanently disabled and stubbed with a tooltip. This occupies valuable real estate while delivering no value.
- **Actionable Fix:** Either implement the asynchronous pause/resume functionality within `pipeline.py` and `ResearchWorker`, or hide the button entirely until the backend logic is complete.

### 2.2 Hardcoded Styling & Accessibility
- **Dark Mode Only / Inline CSS:** Styling is heavily hardcoded across widgets (e.g., `font-size: 20px; font-weight: 700; color: '#8a96a8'`). There is no centralized theme manager for seamless switching to a Light Mode.
- **Window Sizing:** `main_window.py` hardcodes window size to `resize(1320, 860)`. 
- **Actionable Fix:** Move inline CSS styles into a centralized QSS file or expand `theme.py`. Change fixed dimensions to scalable layouts that respect system DPI, using dynamic min/max window policies.

### 2.3 Insufficient Feedback Loops
- **No Global Loading States:** Long-running synchronous tasks (like PDF export via `QTextDocument.print_` or heavy JSON parsing) lock the application window without displaying a loading spinner, overlay, or progress bar. This causes the OS to report the app as "Not Responding".
- **Actionable Fix:** Add a standard indeterminate `QProgressBar` or a loading overlay that triggers during I/O and PDF generation.

---

## 3. Recommended Remediation Plan

Claude Code should execute these tasks in the following priority order:

1. **Refactor QTimer & Threading (High Priority):** 
   - Remove the 3-second `QTimer` in `main_window.py`.
   - Update `dashboard.py` and `history_page.py` to fetch SQLite data via a background `QThread` instead of blocking the main thread.
2. **Eliminate Silent Failures (High Priority):**
   - Perform a global search for `except Exception:` and `# noqa: BLE001`.
   - Replace them with specific error handling and explicit logging routing to the internal `QtLogBridge`.
3. **Decouple GUI Components (Medium Priority):**
   - Replace direct private method calls (like `_on_cancel`) with standard Qt signals.
4. **Abstract CSS and Theming (Medium Priority):**
   - Consolidate inline `setStyleSheet` calls into a single stylesheet manager class to easily enable the upcoming Light Mode mentioned in the README.
5. **Address Feature Stubs (Low Priority):**
   - Implement or hide the Pause button. Add visual spinners for PDF generation and JSON re-indexing.

---

## 4. MVP Refactoring Prompt

Copy and paste the following prompt into Claude Code to execute the Minimum Viable Product (MVP) refactoring:

> **Prompt:**
> Please execute a focused refactoring pass on the `researchhq` codebase to address critical performance and stability issues. Focus strictly on these MVP goals:
> 
> 1. **Fix UI Thread Blocking (Performance):** In `main_window.py`, remove the 3-second `QTimer` that blindly calls `_dashboard.refresh()`. Next, update `dashboard.py` and `history_page.py` so that all database queries and file IO (e.g., `histdb.list_runs`, `histdb.aggregate`, `histdb.reindex_from_folder`) run asynchronously using `QThread` or `QRunnable`/`QThreadPool` instead of blocking the main PySide6 event loop. Emit custom signals (`pyqtSignal` / `Signal`) with the result payload to update the UI safely on the main thread.
> 2. **Fix Dangerous Exception Handling (Stability):** Search for `except Exception:` and `# noqa: BLE001` throughout the project (especially in `main_window.py`, `dashboard.py`, `research_page.py`, and `history.py`). Replace them with targeted exception handling (e.g., `sqlite3.Error`, `json.JSONDecodeError`, `OSError`). For any remaining catch-all blocks, ensure you use `logger.exception("...")` to properly log the stack trace rather than failing silently.
> 3. **Clean Up UI Stubs (UX):** In `research_page.py`, completely hide or remove the "Pause" button (`self._pause_btn`) and its layout spacing, as the feature is currently unhandled and clutters the interface.
> 4. **Add Basic Loading States (UX):** Introduce a simple indeterminate `QProgressBar` or update a status label in the dashboard and history views that activates while your new background DB threads are fetching data, then hides once the signal returns.
> 
> Please modify the necessary files, ensure all PySide6 thread-safety rules are followed (only update UI elements from the main thread via signals), and provide a short summary of the changes once complete.
