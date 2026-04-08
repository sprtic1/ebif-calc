# EID PROJECT HUB — CLAUDE CODE KICKOFF PROMPT
# Copy and paste this entire prompt into Claude Code to start the build

---

Read the CLAUDE.md file in this folder completely before doing anything else.

Then do the following in order, fully autonomously, without stopping for confirmation:

1. Create the /app folder structure exactly as defined in CLAUDE.md

2. Create app/settings.json with placeholder values — I will fill in real 
   paths and API keys before running against a real project

3. Build the Flask backend (app/backend/app.py) with:
   - /api/projects GET — returns list of all projects from projects.json
   - /api/projects POST — creates new project, copies template, registers it
   - /api/projects/:id GET — returns single project details
   - Serves React frontend static build from /frontend/dist in production

4. Build the React frontend (app/frontend/) with EID branding (#868C54 olive,
   #C2C8A2 sage, #F0F2E8 light sage, #737569 warm gray, Lato + Arial Narrow)
   with these pages:
   - Home: list of projects with "New Project" button
   - New Project: form with Project Name, Client Name, Project Number, 
     Dropbox folder path field, and Create button
   - Dashboard: project overview with 16 schedule tiles (all showing 0 for now),
     last synced timestamp, and a prominent "Refresh from Archicad" button

5. Build the template copy service (app/backend/services/template.py) that:
   - Reads templates_folder and projects_folder from settings.json
   - Copies the TEMPLATE .xlsm file to the correct project folder
   - Names it EID-{ProjectNumber}-{ProjectName}.xlsm

6. Create app/data/projects.json to store project registry (start with empty array)

7. Create requirements.txt (Flask, openpyxl, requests, flask-cors)
   and frontend package.json with React, Vite, Tailwind

8. Make sure /pipeline/ and all existing EBIF-CALC files are completely untouched

9. Push everything to GitHub main branch when done

Do not stop between any of these steps. Build the whole thing.
