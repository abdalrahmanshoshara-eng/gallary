from apps.core.errors import AppError


class InvalidImageError(AppError):
    code = "INVALID_IMAGE"
    message = "الملف ليس صورة صالحة. الصيغ المقبولة: JPEG أو PNG أو WebP."


class ImageTooLargeError(AppError):
    code = "IMAGE_TOO_LARGE"
    message = "حجم الصورة أكبر من المسموح."


class ImageTooSmallError(AppError):
    code = "IMAGE_TOO_SMALL"
    message = "أبعاد الصورة صغيرة جداً."
