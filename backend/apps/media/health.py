from apps.core.health import CheckResult, timed_check

from .storage import public_storage


def check_storage() -> CheckResult:
    def _run() -> None:
        storage = public_storage()
        client = storage.connection.meta.client
        client.head_bucket(Bucket=storage.bucket_name)

    return timed_check("storage", _run)
