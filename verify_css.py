import urllib.request
url = 'http://127.0.0.1:8000/static/gestion_transport/style.css'
try:
    with urllib.request.urlopen(url) as r:
        print('STATUS', r.status)
        text = r.read(120).decode('utf-8', errors='replace')
        print(text)
except Exception as e:
    print('ERROR', e)
