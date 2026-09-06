import os
import re
import libsql_client
from playwright.sync_api import sync_playwright
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Environment Variables
TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

PAGES = [
    {"url": "https://dailyintegral.com/play/derivatives/easy", "type": "derivative", "diff": "easy"},
    {"url": "https://dailyintegral.com/play/derivatives/medium", "type": "derivative", "diff": "medium"},
    {"url": "https://dailyintegral.com/play/beginner", "type": "integral", "diff": "beginner"},
    {"url": "https://dailyintegral.com/play/easy", "type": "integral", "diff": "easy"}
]

def get_db_client():
    if not TURSO_URL or not TURSO_TOKEN:
        raise Exception("Missing TURSO_URL or TURSO_TOKEN environment variables")
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

def scrape_problem():
    # Initialize Turso Client
    db = get_db_client()

    try:
        # Ensure table exists
        db.execute('''CREATE TABLE IF NOT EXISTS problems 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, latex TEXT, 
                       type TEXT, difficulty TEXT, hint1 TEXT, hint2 TEXT)''')

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            for item in PAGES:
                page = context.new_page()
                url = item["url"]
                problem_type = item["type"]
                difficulty = item["diff"]

                print(f"\n--- Scraping {difficulty} {problem_type} ---")
                try:
                    page.goto(url, timeout=60000)

                    
                    
                    # 1. Capture Math
                    page.wait_for_selector("annotation", state="attached", timeout=15000)
                    all_parts = page.locator("annotation").all_text_contents()
                    unique_parts = []
                    for part in all_parts:
                        clean_part = part.strip()
                        if "this problem" in clean_part.lower():
                            continue
                        if clean_part not in unique_parts:
                            unique_parts.append(clean_part)
                        # print(clean_part)
                    
                    # Join the remaining parts into the final LaTeX string
                    full_latex = " \\quad ".join(unique_parts)
                    print(f"Math: {full_latex[:50]}...")

                    # 2. Capture Hints
                    hint1, hint2 = None, None
                    selector = "div.font-serif.text-\\[15px\\].leading-7.text-foreground\\/90"

                    # STEP A: Hint 1
                    try:
                        btn1 = page.get_by_role("button", name=re.compile(r"hint 1", re.IGNORECASE))
                        if btn1.count() > 0:
                            btn1.click()
                            page.wait_for_selector(selector, timeout=5000)
                            candidates = page.locator(selector).all_text_contents()
                            for t in candidates:
                                clean_t = t.strip()
                                if "Discord" not in clean_t and "typing" not in clean_t and len(clean_t) > 15:
                                    hint1 = clean_t
                                    break
                            page.get_by_role("button", name="Close hint").click()
                            page.wait_for_timeout(1000)
                    except: pass

                    # STEP B: Hint 2
                    try:
                        page.wait_for_timeout(2000) 
                        btn2 = page.get_by_role("button", name=re.compile(r"hint 2", re.IGNORECASE))
                        label = btn2.get_attribute("aria-label") or ""
                        if btn2.count() > 0 and "locked" not in label.lower():
                            btn2.click()
                            page.wait_for_selector(selector, timeout=5000)
                            candidates_2 = page.locator(selector).all_text_contents()
                            valid_hints = [t.strip() for t in candidates_2 if "Discord" not in t and len(t.strip()) > 15]
                            if len(valid_hints) >= 2: hint2 = valid_hints[1]
                            elif len(valid_hints) == 1 and valid_hints[0] != hint1: hint2 = valid_hints[0]
                            page.get_by_role("button", name="Close hint").click()
                    except: pass

                    # 3. Turso Database Logic
                    today = datetime.now().strftime("%Y-%m-%d")
                    res = db.execute(
                        "SELECT id, hint1, hint2 FROM problems WHERE date=? AND type=? AND difficulty=? AND latex=?",
                        [today, problem_type, difficulty, full_latex]
                    )
                    
                    if not res.rows:
                        db.execute(
                            "INSERT INTO problems (date, latex, type, difficulty, hint1, hint2) VALUES (?, ?, ?, ?, ?, ?)",
                            [today, full_latex, problem_type, difficulty, hint1, hint2]
                        )
                        print("Status: Saved new entry to Turso.")
                    else:
                        row_id = res.rows[0][0]
                        h1_existing = res.rows[0][1]
                        h2_existing = res.rows[0][2]
                        if h1_existing is None and hint1 is not None:
                            db.execute("UPDATE problems SET hint1 = ? WHERE id = ?", [hint1, row_id])
                        if h2_existing is None and hint2 is not None:
                            db.execute("UPDATE problems SET hint2 = ? WHERE id = ?", [hint2, row_id])
                        print("Status: Database synced.")

                except Exception as e:
                    print(f"Error on {url}: {e}")
                
                page.close()

            browser.close()
    
    finally:
        # CRITICAL: This closes the connection and allows the script to exit
        db.close()
        print("\nDatabase connection closed. Scraping session finished.")

if __name__ == "__main__":
    scrape_problem()