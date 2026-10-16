import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
import boto3

load_dotenv()

# Sentry error reporting (oxjob #1685); a missing SENTRY_DSN makes this a no-op. Errors only:
# every unhandled exception becomes a 500 that the Flask integration reports, and a gunicorn
# worker timeout (SystemExit(1) raised mid-request) is reported by its WSGI middleware.
#
# Keep events cheap (oxjob #1711). On a timeout the worker has about a second between gunicorn's
# SIGABRT and its SIGKILL to write the 500. An event with frame locals (the page, the soup tree)
# took ~145 ms CPU to build, several times that on a busy task, so workers died first and the load
# balancer returned 502s. Without locals it takes ~1 ms. No traces_sample_rate: 0 still builds a
# transaction per request.
if os.environ.get("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        send_default_pii=False,
        include_local_variables=False,
    )

from parseland_lib.parse import parse_page, find_pdf_link
from parseland_lib.s3 import get_landing_page_from_r2
from parseland_lib.dynamodb import get_dynamodb_record

app = Flask(__name__)
app.json.sort_keys = False


# A gunicorn worker timeout raises SystemExit(1) mid-request. Answer it with a plain 500 right here, below
# Sentry's middleware, so the worker writes its response at once, as it did before Sentry: building a Sentry
# event first sometimes outlasted the master's SIGKILL, and the load balancer returned 502 (oxjob #1711).
# The worker still exits after this request; ox-logs shows each "WORKER TIMEOUT".
def _answer_timeouts(wsgi_app):
    def wrapped(environ, start_response):
        try:
            return wsgi_app(environ, start_response)
        except SystemExit:
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"worker timeout"]
    return wrapped


app.wsgi_app = _answer_timeouts(app.wsgi_app)

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
    namespace = data.get('namespace')
    resolved_url = data.get('resolved_url')
    response = parse_page(data['html'], namespace, resolved_url)
    return jsonify(response)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)