import os
import fnmatch
from io import StringIO
from dotenv import load_dotenv
from pathlib import Path
from cryptography.fernet import Fernet
import hashlib


ENCRYPTED_PATH = "./.encrypted"

PLAINTEXT_SECRETS = {
    "production": [
        "./production.env",
    ],
    "staging": [
        "./staging.env",
    ],
    "development": [
        "./.env",
    ],
}


def get_name_digest(env, filename):
    """Returns environment and file hex digest

    Args:
        env ([type]): [description]
        filename ([type]): [description]

    Returns:
        [type]: [description]
    """
    m = hashlib.shake_256()
    m.update(f"{env}||{filename}".encode())
    return m.hexdigest(32), m.hexdigest(4)


def get_environment() -> str:
    return os.environ.get("ENV", "development")


def load_credentials(credentials) -> None:
    """Load decrypred credentials into environment

    Args:
        credentials (list): Decrypted credentials from decrypt_credentials
    """
    if credentials:
        for credential_string in credentials:
            filelike = StringIO(credential_string)
            filelike.seek(0)
            print("loading envs")
            load_dotenv(stream=filelike)


def decrypt_credentials(env=None, which=None, encrypted_path=None, secrets_map=None) -> list:
    """Decrypt credentials from specified environment, a filter of which credentials to decrypt,
    path to encrypted credentials, and map of encrypted files.

    Args:
        env ([type], optional): [description]. Defaults to None.
        which ([type], optional): [description]. Defaults to None.
        encrypted_path ([type], optional): [description]. Defaults to None.
        secrets_map ([type], optional): [description]. Defaults to None.

    Returns:
        list: [description]
    """
    if secrets_map is None:
        secrets_map = PLAINTEXT_SECRETS
    if encrypted_path is None:
        encrypted_path = ENCRYPTED_PATH
    if env is None:
        env = get_environment()
    secret_key = os.environ.get(f"APP_SECRET_{env.upper()}", None)
    integrity_checks = (
        secret_key is None,
        secret_key == "",
        env is None,
        env == "",
    )
    if any(integrity_checks):
        print("[Pysecrets] No secrets will be loaded")
        return None
    f = Fernet(secret_key)

    decrypted = []
    files_to_decrypt = secrets_map.get(env)
    if files_to_decrypt is None:
        return decrypted

    for file_to_decrypt in files_to_decrypt:
        if which:
            if not any([fnmatch.fnmatch(file_to_decrypt, x) for x in which]):
                continue
        filekey, digest = get_name_digest(env, file_to_decrypt)
        path = Path(encrypted_path, filekey)
        try:
            fp = open(path, "rb")
            secret = fp.read()
            fp.close()
            credential = f.decrypt(secret).decode("utf-8")
            decrypted.append(credential)
            print(f"   ...Decrypted successfully. Digest: {digest}")
        except:
            print(f"   Secret not found. Digest: {digest}")
            print("   No secret was loaded")
    return decrypted


def rotate_credentials(env, encrypted_path=None, secrets_map=None):
    """Rotate credentials

    Args:
        env ([type]): environment identifier
        encrypted_path ([type], optional): [description]. Defaults to None.
        secrets_map ([type], optional): [description]. Defaults to None.

    Raises:
        RuntimeError: Environment isn't set properly
    """
    if env is None or env == "":
        raise RuntimeError("Environment was not explicitly specified during credentials rotation")
    secret_key = Fernet.generate_key()
    replace_credentials(secret_key, env, encrypted_path, secrets_map)
    fp = open("./.secrets/key", "wb")
    fp.write(secret_key)
    fp.close()
    print("   Secret key replaced in .secrets/key")


def encrypt_credentials(env: str, encrypted_path=None, secrets_map=None):
    """Decrypt credentials

    Args:
        env (str): [description]
        encrypted_path ([type], optional): [description]. Defaults to None.
        secrets_map ([type], optional): [description]. Defaults to None.

    Raises:
        RuntimeError: [description]
        Exception: [description]

    Returns:
        [type]: [description]
    """
    if env is None or env == "":
        raise RuntimeError("Environment was not explicitly specified during encryption")
    secret_key = os.environ.get(f"APP_SECRET_{env.upper()}", None)
    if secret_key is None:
        raise Exception(f"{env}: No APP_SECRET_{env.upper()} variable found for specified environment")
    return replace_credentials(secret_key, env, encrypted_path, secrets_map)


def replace_credentials(secret_key: str, env: str, encrypted_path=None, secrets_map=None):
    if secrets_map is None:
        secrets_map = PLAINTEXT_SECRETS
    if encrypted_path is None:
        encrypted_path = ENCRYPTED_PATH
    integrity_checks = (
        secret_key is None,
        secret_key == "",
        env is None,
        env == "",
    )
    if any(integrity_checks):
        raise RuntimeError("Bad parameter received when replacing credentials")
    f = Fernet(secret_key)
    files_to_encrypt = secrets_map.get(env)
    for _, file_to_encrypt in enumerate(files_to_encrypt):
        filekey, digest = get_name_digest(env, file_to_encrypt)
        path_from = Path(file_to_encrypt)
        path_to = Path(encrypted_path, filekey)
        fp = open(path_from, "rb")
        secret = fp.read()
        fp.close()
        encrypted = f.encrypt(secret)
        fp = open(path_to, "wb")
        fp.write(encrypted)
        fp.close()
        print(f"   ...Encrypted secret. Digest: {digest}")
