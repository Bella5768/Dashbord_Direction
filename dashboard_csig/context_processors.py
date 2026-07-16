import os


def cloudinary_settings(request):
    return {
        'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME', ''),
        'CLOUDINARY_UPLOAD_PRESET': os.getenv('CLOUDINARY_UPLOAD_PRESET', ''),
    }
