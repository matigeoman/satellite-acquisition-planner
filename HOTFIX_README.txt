Stage 17.2 hotfix: Streamlit time_input step

Fix:
- app/ui/pages/live_tracking.py
- changes the time_input step from 30 seconds to 1 minute
- adds a regression test in tests/test_live_tracking_ui_architecture.py

Apply in repository root:
Expand-Archive -Path .\satplan-stage17-2-time-input-hotfix.zip -DestinationPath . -Force

Then test:
$Python = "$HOME\.conda\envs\satplan\python.exe"
& $Python -m pytest tests/test_live_tracking_ui_architecture.py -q
& $Python -m pytest -q
& $Python -m ruff check app tests streamlit_app.py scripts

Docker:
docker compose down
docker compose up --build -d
Start-Sleep -Seconds 15
docker compose ps
