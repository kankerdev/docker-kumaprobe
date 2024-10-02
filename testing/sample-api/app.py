#!/usr/bin/env bash
from flask import Flask
import sys

app = Flask(__name__)

@app.route("/", methods=['GET'])
def respond():
    print("Recieved a request! Exiting.")
    sys.exit(0)

if __name__ == "__main__":
    app.run(host="0.0.0.0")