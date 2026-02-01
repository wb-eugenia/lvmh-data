import json
from pathlib import Path

def verify():
    path = Path('outputs/batch_run_400.json')
    if not path.exists():
        print("❌ File not found")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for i, note in enumerate(data[:3]):
        meta = note.get('meta_analysis', {})
        score = meta.get('quality_score')
        feedback = meta.get('advisor_feedback')
        print(f"Note {i}: Score={score}, Feedback={feedback}")

if __name__ == "__main__":
    verify()
