import requests

with open('test_dup.csv', 'rb') as f:
    files = {'file': ('test_dup.csv', f, 'text/csv')}
    resp = requests.post('http://127.0.0.1:8081/api/data-cleaning', files=files)
    data = resp.json()
    print('Report:', data['report'])
