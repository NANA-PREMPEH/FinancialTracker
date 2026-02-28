import urllib.request
import urllib.parse
import http.cookiejar
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    u = User.query.get(1)
    email = u.email

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

resp = opener.open('http://127.0.0.1:5001/auth/login')
html = resp.read().decode('utf-8')
csrf_token = ''
for line in html.split('\n'):
    if 'name="csrf_token"' in line:
        parts = line.split('value="')
        if len(parts) > 1:
            csrf_token = parts[1].split('"')[0]
            break

data = {
    'email': email,
    'password': 'password',
    'csrf_token': csrf_token
}
encoded_data = urllib.parse.urlencode(data).encode('utf-8')
try:
    req = urllib.request.Request('http://127.0.0.1:5001/auth/login', data=encoded_data)
    resp = opener.open(req)
except Exception as e:
    print("Login error:", e)

resp = opener.open('http://127.0.0.1:5001/')
dash_html = resp.read().decode('utf-8')

for line in dash_html.split('\n'):
    if 'Total Expenses' in line or 'data-amount="GHS' in line:
        print(line.strip())
