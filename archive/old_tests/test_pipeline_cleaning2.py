import requests

with open('test_fillers.csv', 'rb') as f:
    files = {'file': ('test_fillers.csv', f, 'text/csv')}
    data = {'text_column': 'Transcription'}
    resp = requests.post('http://127.0.0.1:9001/api/data-cleaning', files=files, data=data)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
