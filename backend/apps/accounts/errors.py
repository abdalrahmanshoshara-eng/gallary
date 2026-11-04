from rest_framework import status

from apps.core.errors import AppError, ConflictError, PermissionDeniedError


class OtpUnavailableError(AppError):
    code = "OTP_UNAVAILABLE"
    message = "تسجيل الدخول غير متاح حالياً. يرجى المحاولة لاحقاً."
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class OtpRateLimitedError(AppError):
    code = "OTP_RATE_LIMITED"
    message = "طلبت رموزاً كثيرة. انتظر قليلاً ثم حاول مجدداً."
    http_status = status.HTTP_429_TOO_MANY_REQUESTS


class OtpInvalidError(AppError):
    code = "OTP_INVALID"
    message = "الرمز غير صحيح."


class OtpExpiredError(AppError):
    code = "OTP_EXPIRED"
    message = "انتهت صلاحية الرمز أو لم يُطلب بعد. اطلب رمزاً جديداً."


class AccountDisabledError(PermissionDeniedError):
    code = "ACCOUNT_DISABLED"
    message = "هذا الحساب غير مفعّل. تواصل مع إدارة المنصة."


class SelfModificationError(ConflictError):
    code = "SELF_MODIFICATION_FORBIDDEN"
    message = "لا يمكنك تنفيذ هذه العملية على حسابك."


class LastSuperAdminError(ConflictError):
    code = "LAST_SUPER_ADMIN"
    message = "يجب أن يبقى مدير عام واحد على الأقل."


class InvalidCredentialsError(AppError):
    code = "INVALID_CREDENTIALS"
    message = "رقم الهاتف أو كلمة المرور غير صحيحة."
    http_status = status.HTTP_400_BAD_REQUEST


class LoginLockedError(AppError):
    code = "LOGIN_LOCKED"
    message = "محاولات دخول خاطئة كثيرة. انتظر 15 دقيقة ثم حاول مجدداً."
    http_status = status.HTTP_429_TOO_MANY_REQUESTS


class PhoneInUseError(ConflictError):
    code = "PHONE_IN_USE"
    message = "هذا الرقم مسجّل بالفعل. سجّل الدخول بدلاً من ذلك."


class WrongPasswordError(AppError):
    code = "WRONG_PASSWORD"
    message = "كلمة المرور الحالية غير صحيحة."
    http_status = status.HTTP_400_BAD_REQUEST
