from api.main import app
import json
paths = [route.path for route in app.routes]
print(json.dumps(paths))
