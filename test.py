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
    Parse a definite LaTeX integral and calculate its numerical answer fast.
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

    # 3. DIRECT NUMERICAL INTEGRATION:
    # Do NOT call parsed_expr.doit()! Calling .evalf() directly on an unevaluated
    # Integral runs numerical quadrature (mpmath), which takes milliseconds.
    approximate_answer = parsed_expr.evalf()

    # Fallback only if evalf didn't automatically resolve it
    if not approximate_answer.is_number:
        approximate_answer = parsed_expr.doit().evalf()

    # 4. Strip negligible imaginary noise (e.g., 0.0 + 1e-20*I)
    real_part = sympy.re(approximate_answer)
    print("Numerical Answer:", real_part)

    return float(real_part)


async def main():
    client = libsql_client.create_client(
        url=TURSO_URL,
        auth_token=TURSO_TOKEN
    )

    try:
        result = await client.execute("""
            SELECT id, latex
            FROM problems
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
                # Wrap in asyncio.to_thread and wait_for to enforce a 10-second timeout
                answer = await asyncio.wait_for(
                    asyncio.to_thread(compute_answer, latex_question),
                    timeout=10.0
                )

                await client.execute(
                    """
                    UPDATE problems
                    SET answer = ?
                    WHERE id = ?
                    """,
                    [answer, problem_id]
                )

                print(f"Successfully updated problem ID {problem_id}: {answer}")

            except asyncio.TimeoutError:
                print(f"Timed out after 10s on problem ID {problem_id}, skipping.")
            except Exception as e:
                print(f"Failed to solve problem ID {problem_id}: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
    
    
