import requests

with open('test_dup.csv', 'rb') as f:
    files = {'file': ('test_dup.csv', f, 'text/csv')}
    resp = requests.post('http://127.0.0.1:8081/api/data-cleaning', files=files)
    data = resp.json()
    print('=' * 50)
    print('RESULTAT DU NETTOYAGE')
    print('=' * 50)
    print(f"Original: {data['report']['original_rows']} lignes")
    print(f"Final: {data['report']['final_rows']} lignes")
    print(f"Supprime: {data['report']['rows_removed_total']} lignes")
    print(f"Reduction: {data['report']['reduction_percent']}%")
    print()
    print('DETAILS:')
    for d in data['report']['details']:
        print(f'  - {d}')
