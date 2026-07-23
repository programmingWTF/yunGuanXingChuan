import ast
import sys

files = [
    'src/agents/science_agent.py',
    'src/llm_client.py',
    'src/search/tavily_search.py',
    'src/pipeline.py',
    'api/routes/analyze.py',
]

for f in files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f"  OK: {f}")
    except SyntaxError as e:
        print(f"  FAIL: {f} -> {e}")
        sys.exit(1)

print("\nAll files syntax OK!")
