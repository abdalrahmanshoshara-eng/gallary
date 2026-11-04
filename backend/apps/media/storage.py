from django.core.files.storage import Storage, storages


def public_storage() -> Storage:
    return storages["default"]


def private_storage() -> Storage:
    return storages["private"]
