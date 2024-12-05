from gzip import decompress
from urllib.parse import quote
import boto3
import botocore

from parseland_lib.exceptions import S3FileNotFoundError

S3_LANDING_PAGE_BUCKET = 'openalex-harvested-content'


def make_s3(aws_access_key_id=None, aws_secret_access_key=None, region_name=None):
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name
    )
    return session.client('s3')


def get_obj(bucket, key, s3):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] in {"404", "NoSuchKey"}:
            raise S3FileNotFoundError()


def get_key(url: str):
    return quote(url.lower()).replace('/', '_')


def is_pdf_in_s3(bucket, key, s3):
    try:
        resp = s3.get_object(
            Bucket=bucket,
            Key=key,
            Range='bytes=0-4'  # %PDF- is 5 bytes
        )
        content = resp['Body'].read()
        return content.startswith(b'%PDF-')
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] in {"404", "NoSuchKey"}:
            raise S3FileNotFoundError()


def get_landing_page_from_s3(url, s3=None):
    if not s3:
        s3 = make_s3()
    key = get_key(url)

    # Check if PDF before downloading whole file
    if is_pdf_in_s3(S3_LANDING_PAGE_BUCKET, key, s3):
        return None

    obj = get_obj(S3_LANDING_PAGE_BUCKET, key, s3)
    content = obj['Body'].read()

    try:
        # check if content starts with gzip magic number
        if content.startswith(b'\x1f\x8b\x08'):
            return decompress(content)
        # if not compressed, return as is
        return content
    except Exception as e:
        print(f"Error decompressing content for {url}: {str(e)}")
        # Return uncompressed content as fallback
        return content


def is_pdf(contents: bytes):
    return contents.startswith(b"%PDF-")
