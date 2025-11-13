# app.py
import os
from flask import Flask, send_file, send_from_directory, abort

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
ASSETS_DIR = os.path.join(PUBLIC_DIR, "assets")
TEST_HTML_PATH = os.path.join(PUBLIC_DIR, "test.html")


@app.route("/test.html")
def test_html():
    if not os.path.exists(TEST_HTML_PATH):
        abort(404)
    return send_file(TEST_HTML_PATH)


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    return send_from_directory(ASSETS_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
