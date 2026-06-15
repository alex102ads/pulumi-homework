from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def index():
    val = os.environ.get("CUSTOM_VALUE", "unset")
    return f"<html><body><h1>Custom value: {val}</h1></body></html>"