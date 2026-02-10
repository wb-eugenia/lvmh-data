import requests

with open('test_fillers.csv', 'rb') as f:
    files = {'file': ('test_fillers.csv', f, 'text/csv')}
    data = {'text_column': 'Transcription'}
    resp = requests.post('http://127.0.0.1:9002/api/data-cleaning', files=files, data=data)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"\nOriginal: {result['report']['original_rows']} lignes")
        print(f"Final: {result['report']['final_rows']} lignes")
        print(f"Reduction: {result['report']['reduction_percent']}%")
        print("\nDetails:")
        for d in result['report']['details']:
            print(f"  - {d}")
    else:
        print(f"Error: {resp.text}")
