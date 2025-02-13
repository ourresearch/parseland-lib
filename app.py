from flask import Flask, jsonify, request
import boto3
from css_limiter import install_css_limiter, CSSLimitExceeded

from parseland_lib.parse import parse_page
from parseland_lib.s3 import get_landing_page_from_s3, get_resolved_url

app = Flask(__name__)
app.json.sort_keys = False

css_limiter = install_css_limiter()

@app.before_request
def before_request():
    # reset the CSS counter before each request
    css_limiter.reset()

s3_client = boto3.client("s3", region_name="us-east-1")
dynamodb_client = boto3.client("dynamodb", region_name="us-east-1")

@app.route("/")
def index():
    return jsonify({
        "version": "0.1",
        "msg": "Parser is running"
    })

@app.route("/parseland/<uuid:harvest_id>", methods=['GET'])
def parse_landing_page(harvest_id):
    try:
        css_limiter.reset()  # Reset counter at start of request

        lp = get_landing_page_from_s3(harvest_id, s3_client)
        resolved_url = get_resolved_url(harvest_id, dynamodb_client)

        if lp is None:
            return jsonify({
                "msg": "No landing page found"
            }), 404

        response = parse_page(lp, resolved_url)
        return jsonify(response)

    except CSSLimitExceeded as e:
        # return 400 since this is essentially a "bad request" - too complex to parse
        return jsonify({
            "error": "CSS selector limit exceeded",
            "message": str(e),
            "call_count": css_limiter._call_count,
            "type": "css_limit_exceeded"
        }), 400


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