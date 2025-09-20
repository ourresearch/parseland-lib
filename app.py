import os

from flask import Flask, jsonify, request
import boto3

from parseland_lib.parse import parse_page, find_pdf_link
from parseland_lib.s3 import get_landing_page_from_r2
from parseland_lib.dynamodb import get_dynamodb_record

app = Flask(__name__)
app.json.sort_keys = False

r2_account_id = os.environ.get('R2_ACCOUNT_ID')
r2_access_key = os.environ.get('R2_ACCESS_KEY_ID')
r2_secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')

s3_client = boto3.client(
    's3',
    endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
    aws_access_key_id=r2_access_key,
    aws_secret_access_key=r2_secret_key,
    region_name='auto'  # R2 uses 'auto' as region
)
dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")

@app.route("/")
def index():
    return jsonify({
        "version": "0.1",
        "msg": "Parser is running"
    })

@app.route("/parseland/<uuid:harvest_id>", methods=['GET'])
def parse_landing_page(harvest_id):
    lp = get_landing_page_from_r2(harvest_id, s3_client)
    if lp is None:
        return jsonify({
            "msg": "No landing page found"
        }), 404

    dynamo_record = get_dynamodb_record(harvest_id, dynamodb_client)
    namespace = dynamo_record['namespace']
    resolved_url = dynamo_record['resolved_url']

    response = parse_page(lp, namespace, resolved_url)
    return jsonify(response)

@app.route("/parseland/find-pdf/<uuid:harvest_id>", methods=['GET'])
def get_pdf_url(harvest_id):
    lp = get_landing_page_from_r2(harvest_id, s3_client)

    dynamo_record = get_dynamodb_record(harvest_id, dynamodb_client)
    namespace = dynamo_record['namespace']
    resolved_url = dynamo_record['resolved_url']

    pdf_link = find_pdf_link(lp, namespace, resolved_url)

    if pdf_link is None:
        return jsonify({
            "msg": "No PDF link found"
        }), 404
    return jsonify({
        "pdf_url": pdf_link
    })


@app.route("/parseland", methods=['POST'])
def parse_landing_page_raw():
    data = request.get_json()
    if 'html' not in data:
        return jsonify({
            "msg": "No html in request body"
        }), 400
    response = parse_page(data['html'], None)
    return jsonify(response)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)