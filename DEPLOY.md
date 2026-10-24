# Deploy SmartBus AI (free) on Render
1. Create a GitHub repo and push this folder (git init; git add .; git commit -m init; git push).
2. render.com -> New -> Web Service -> connect the repo (render.yaml is detected).
3. Build: `pip install -r requirements.txt && python ml/train.py`   Start: `gunicorn app:app`
4. Open the *.onrender.com URL. Free instances sleep after inactivity (first load ~30 s).
Notes: SQLite resets on redeploy on free hosting; use PostgreSQL for permanent data.
Alternative: PythonAnywhere (free) - upload the folder, create a Flask web app, point WSGI to `app`.
