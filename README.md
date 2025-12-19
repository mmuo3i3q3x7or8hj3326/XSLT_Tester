# XSLT Tester (Created in [Gemini CLI](https://docs.cloud.google.com/gemini/docs/codeassist/gemini-cli))

A simple, standalone desktop application for XSLT development and transformation testing.


![XSLT_Tester](https://raw.githubusercontent.com/mmuo3i3q3x7or8hj3326/XSLT_Tester/refs/heads/main/screenshot.png "Sample image of the app running in Dark Mode")

## Features
-   XPath copy pasting
-   Right-click > Format: Pretty-printing for XML/XSLT.
-   No word-wrapping for readability.
-   Dark Theme if detects Windows Dark Mode

## Building from Source

To build and run this application from the source code, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd XSLT_Tester
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    # On Windows
    python -m venv venv
    .\venv\Scripts\activate

    # On macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Inside venv, install the required dependencies:**
    ```bash
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

4.  **Inside venv, run the application:**
    ```bash
    python main.py
    ```

## For Windows .exe

    pyinstaller --onefile --windowed --name XSLT_Tester --icon="icon.ico" --add-data="icon.ico;." main.py

## Releases

Pre-built binaries for Windows are available on the [**Releases**](https://github.com/mmuo3i3q3x7or8hj3326/XSLT_Tester/releases) page of this repository.

