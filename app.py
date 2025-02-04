from flask import Flask, jsonify
import boto3

from parseland_lib.parse import parse_page
from parseland_lib.s3 import get_landing_page_from_s3, get_resolved_url

app = Flask(__name__)
app.json.sort_keys = False

s3_client = boto3.client("s3", region_name="us-east-1")
dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")

@app.route("/")
def index():
    return jsonify({
        "version": "0.1",
        "msg": "Parser is running"
    })

@app.route("/parse/<uuid:harvest_id>", methods=['GET'])
def parse_landing_page(harvest_id):
    lp = get_landing_page_from_s3(harvest_id, s3_client)
    resolved_url = get_resolved_url(harvest_id, dynamodb_client)
    if lp is None:
        return jsonify({
            "msg": "No landing page found"
        }), 404
    response = parse_page(lp, resolved_url)
    return jsonify(response)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)