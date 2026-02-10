import requests

with open('test_fillers.csv', 'rb') as f:
    files = {'file': ('test_fillers.csv', f, 'text/csv')}
    data = {'text_column': 'Transcription'}
    resp = requests.post('http://127.0.0.1:9001/api/data-cleaning', files=files, data=data)
    result = resp.json()
    print('=' * 60)
    print('RESULTAT DU NETTOYAGE AVEC PIPELINE LVMH')
    print('=' * 60)
    print(f"Original: {result['report']['original_rows']} lignes")
    print(f"Final: {result['report']['final_rows']} lignes")
    print(f"Reduction: {result['report']['reduction_percent']}%")
    print()
    print('DETAILS:')
    for d in result['report']['details']:
        print(f'  - {d}')
