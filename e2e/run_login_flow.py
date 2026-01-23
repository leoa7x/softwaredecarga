import time
import subprocess
import sys
import os
import pyautogui as pag

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "camiones_gui.py"))

# Safety
pag.FAILSAFE = True

# Start app
p = subprocess.Popen([sys.executable, APP])

# Wait for window
time.sleep(3)

# Click username field and type
pag.click(230, 250)
pag.write("admin", interval=0.05)

# Click password field and type
pag.click(230, 310)
pag.write("admin123", interval=0.05)

# Click login button
pag.click(230, 380)

# Wait for main window
time.sleep(3)

# Exit app
pag.hotkey("command", "q")
