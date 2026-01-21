
import json
import sys

park_code = sys.argv[1] if len(sys.argv) > 1 else "BRCA"
path = f"data_samples/nps/raw/{park_code}/raw_trails.json"
try:
    with open(path, 'r') as f:
        data = json.load(f)
        count = len(data.get('data', [])) if isinstance(data, dict) else len(data)
        print(f"EXISTING COUNT: {count}")
except Exception as e:
    print(f"Error ({park_code}): {e}")
