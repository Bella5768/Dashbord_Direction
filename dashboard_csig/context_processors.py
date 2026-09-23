import os


def aws_media_settings(request):
    return {
        'AWS_S3_REGION': os.getenv('AWS_S3_REGION', ''),
        'AWS_STORAGE_BUCKET_NAME': os.getenv('AWS_STORAGE_BUCKET_NAME', ''),
        'AWS_CLOUDFRONT_DOMAIN': os.getenv('AWS_CLOUDFRONT_DOMAIN', ''),
    }