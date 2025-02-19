@echo off
echo Activating virtual environment...
call venv\Scripts\activate

echo Starting Flask server (app.py)...
start python app.py

echo Starting keylogger client (main.py)...
start python main.py

echo Both server and client have been started.
