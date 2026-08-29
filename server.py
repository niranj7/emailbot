import os
from api.index import app

if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 3000))
    print(f"Draftly is running at http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
