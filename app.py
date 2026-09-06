import os
from flask import Flask, render_template, request
import libsql_client
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

# Helper function to query Turso and return results as dictionaries
# This keeps your existing HTML templates working without changes!
def query_db(query, args=None):
    client = libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    try:
        res = client.execute(query, args or [])
        # Convert the Resultset into a list of dictionaries
        columns = res.columns
        return [dict(zip(columns, row)) for row in res.rows]
    finally:
        client.close()

def get_category_counts():
    # We query counts. Note: [0][0] gets the first column of the first row
    counts = {}
    
    q_base = "SELECT COUNT(*) FROM problems WHERE type=? AND difficulty=?"
    
    counts['easy_derivative'] = query_db(q_base, ["derivative", "easy"])[0]['COUNT(*)']
    counts['medium_derivative'] = query_db(q_base, ["derivative", "medium"])[0]['COUNT(*)']
    counts['beginner_integral'] = query_db(q_base, ["integral", "beginner"])[0]['COUNT(*)']
    counts['easy_integral'] = query_db(q_base, ["integral", "easy"])[0]['COUNT(*)']
    
    return counts

@app.context_processor
def inject_counts():
    # This automatically makes 'counts' available in every HTML template
    return {'counts': get_category_counts()}

@app.route('/')
def index():
    # Fetch the most recent date
    date_res = query_db("SELECT MAX(date) as last_date FROM problems")
    latest_date = date_res[0]['last_date'] if date_res else None
    
    problems = []
    if latest_date:
        raw_problems = query_db("SELECT * FROM problems WHERE date = ? ORDER BY id DESC", [latest_date])
        # Mark problems with lengthy LaTeX as large
        problems = [dict(p, large=len(p['latex']) > 120) for p in raw_problems]
    
    return render_template('index.html', title='Welcome to MathVault', problems=problems)

@app.route('/derivatives/easy')
def easy_derivatives():
    raw_problems = query_db("SELECT * FROM problems WHERE type='derivative' AND difficulty='easy' ORDER BY date DESC")
    problems = [dict(p, large=len(p['latex']) > 120) for p in raw_problems]
    return render_template('easy_derivatives.html', problems=problems, title="Easy Derivatives")

@app.route('/derivatives/medium')
def medium_derivatives():
    raw_problems = query_db("SELECT * FROM problems WHERE type='derivative' AND difficulty='medium' ORDER BY date DESC")
    problems = [dict(p, large=len(p['latex']) > 120) for p in raw_problems]
    return render_template('medium_derivatives.html', problems=problems, title="Medium Derivatives")

@app.route('/integrals/easy')
def easy_integrals():
    raw_problems = query_db("SELECT * FROM problems WHERE type='integral' AND difficulty='easy' ORDER BY date DESC")
    problems = [dict(p, large=len(p['latex']) > 120) for p in raw_problems]
    return render_template('easy_integrals.html', problems=problems, title="Easy Integrals")

@app.route('/integrals/beginner')
def beginner_integrals():
    raw_problems = query_db("SELECT * FROM problems WHERE type='integral' AND difficulty='beginner' ORDER BY date DESC")
    problems = [dict(p, large=len(p['latex']) > 120) for p in raw_problems]
    return render_template('beginner_integrals.html', problems=problems, title="Beginner Integrals")

@app.route('/problem/<int:problem_id>')
def problem_detail(problem_id):
    problem_res = query_db('SELECT * FROM problems WHERE id = ?', [problem_id])
    if not problem_res:
        return "Problem not found", 404
    return render_template('problem_detail.html', problem=problem_res[0])

if __name__ == '__main__':
    app.run(debug=True)