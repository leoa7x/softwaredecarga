# E2E GUI Tests (Mac)

These tests use `pyautogui` and require screen access permissions.

## Setup

```bash
pip install pyautogui
```

Allow the terminal (or Python) in **System Settings → Privacy & Security → Accessibility** and **Screen Recording**.

## Run

```bash
python3 e2e/run_login_flow.py
```

## Notes
- Coordinates are hardcoded for 460x520 login window. Adjust if needed.
- Ensure the app window is in focus.
- Press `Cmd+Q` to quit if script fails.
