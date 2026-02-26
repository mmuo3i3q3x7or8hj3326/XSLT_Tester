@echo off
python -c "import PySide6, saxonche, pygments, lxml, darkdetect" 2>nul
if %errorlevel% neq 0 (
    python -m pip install -r requirements.txt
)
start "" pythonw main.py