import asyncio
import os
import re
from dotenv import load_dotenv
import libsql_client
import sympy
from sympy.parsing.latex import parse_latex

# Load environment variables
load_dotenv()

TURSO_URL = os.getenv("TURSO_URL")
TURSO_TOKEN = os.getenv("TURSO_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    raise ValueError("Missing TURSO_URL or TURSO_TOKEN environment variables")


def clean_latex(latex_str: str) -> str:
    """Removes common LaTeX wrapper syntax like $, $$, \\[, \\]"""
    cleaned = latex_str.strip()
    cleaned = re.sub(r"^(\$\$|\$|\\\[|\\\()", "", cleaned)
    cleaned = re.sub(r"(\$\$|\$|\\\]|\\\))$", "", cleaned)
    return cleaned.strip()


def compute_answer(latex_integral: str) -> float:
    """
    Parse a definite LaTeX integral and return its numerical floating-point answer.
    """
    cleaned = clean_latex(latex_integral)
    print(f"\nProcessing: {cleaned}")

    # 1. Parse LaTeX into SymPy
    parsed_expr = parse_latex(cleaned)

    # 2. Map standard mathematical constants
    parsed_expr = parsed_expr.subs({
        sympy.Symbol("pi"): sympy.pi,
        sympy.Symbol("e"): sympy.E
    })

    # 3. Evaluate the definite integral
    exact_solution = parsed_expr.doit()
    print("Exact Answer:", exact_solution)

    # 4. Numerically approximate and return as float
    approximate_answer = exact_solution.evalf()
    print("Decimal Approximation:", approximate_answer)

    return float(approximate_answer)


async def main():
    client = libsql_client.create_client(
        url=TURSO_URL,
        auth_token=TURSO_TOKEN
    )

    try:
        # Strictly queries beginner integrals with no answer yet
        result = await client.execute("""
            SELECT id, latex
            FROM integrals
            WHERE type = 'integral'
              AND difficulty = 'beginner'
              AND answer IS NULL
        """)

        problems = result.rows
        print(f"Found {len(problems)} unanswered beginner integrals.")

        for problem in problems:
            problem_id = problem[0]
            latex_question = problem[1]

            try:
                answer = compute_answer(latex_question)

                await client.execute(
                    """
                    UPDATE integrals
                    SET answer = ?
                    WHERE id = ?
                    """,
                    [answer, problem_id]
                )

                print(f"Updated problem ID {problem_id}: {answer}")

            except Exception as e:
                print(f"Failed to solve problem ID {problem_id}: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
