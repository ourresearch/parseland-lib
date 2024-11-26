import os
from gzip import decompress
from urllib.parse import quote

import boto3
import botocore

from parseland_lib.exceptions import S3FileNotFoundError

S3_LANDING_PAGE_BUCKET = 'openalex-harvested-content'


def make_s3():
    session = boto3.session.Session()
    return session.client('s3',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv(
                              'AWS_SECRET_ACCESS_KEY'),
                          region_name=os.getenv('AWS_DEFAULT_REGION'))


DEFAULT_S3 = make_s3()


def get_obj(bucket, key, s3=DEFAULT_S3):
    try:
        obj = s3.get_object(Bucket=bucket,
                            Key=key)
        return obj
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] in {"404", "NoSuchKey"}:
            raise S3FileNotFoundError()


def get_key(url: str):
    return quote(url.lower()).replace('/', '_')


def get_landing_page_from_s3(url, s3=DEFAULT_S3):
    if not s3:
        s3 = DEFAULT_S3
    key = get_key(url)
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
