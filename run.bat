@echo off
python -c "import PySide6, saxonche, pygments, lxml, darkdetect" 2>nul
if %errorlevel% neq 0 (
    echo Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
)
start "" pythonw main.py
