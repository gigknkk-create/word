import os
import urllib.request
import json
import sys

def check_progress():
    repo = "gigknkk-create/word"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Mozilla/5.0"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # 1. Fetch latest workflow run (works publicly without token)
    runs_url = f"https://api.github.com/repos/{repo}/actions/runs?per_page=3"
    req = urllib.request.Request(runs_url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error connecting to GitHub: {e}")
        return

    runs = data.get("workflow_runs", [])
    if not runs:
        print("No workflow runs found.")
        return

    latest_run = runs[0]
    run_id = latest_run["id"]
    status = latest_run["status"]
    conclusion = latest_run["conclusion"]
    started_at = latest_run.get("run_started_at", "Unknown")

    print(f"\n=======================================================")
    print(f"Latest Workflow Run: ID #{run_id}")
    print(f"Status: {status.upper()} | Conclusion: {conclusion}")
    print(f"Started At: {started_at}")
    print(f"Run Link: https://github.com/{repo}/actions/runs/{run_id}")
    print(f"=======================================================")

    if status == "in_progress":
        # Fetch job steps
        jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
        req_jobs = urllib.request.Request(jobs_url, headers=headers)
        with urllib.request.urlopen(req_jobs) as resp:
            jobs_data = json.loads(resp.read().decode())

        for job in jobs_data.get("jobs", []):
            print(f"\nJob: {job['name']} [{job['status']}]")
            for step in job.get("steps", []):
                print(f"  * {step['name']}: {step['status']}")

        print("\nTip: To view real-time streaming page-by-page progress, open the Run Link above in your browser!")
    elif status == "completed":
        print(f"\nWorkflow has completed with result: {conclusion.upper()}")
        print("Check 'datasets/' folder for the generated vocabulary files!")

if __name__ == "__main__":
    check_progress()
