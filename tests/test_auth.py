import pytest

from services.auth import hash_password, verify_password
from services.errors import PasswordTooLongError


def test_hash_password_returns_different_string_than_input():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_incorrect_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_password_rejects_passwords_over_72_bytes():
    long_password = "a" * 73
    with pytest.raises(PasswordTooLongError):
        hash_password(long_password)


def test_hash_password_accepts_password_at_72_byte_limit():
    password = "a" * 72
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_hash_password_counts_bytes_not_characters():
    # Each "é" is 2 bytes in UTF-8, so 40 of them is 80 bytes.
    long_password = "é" * 40
    with pytest.raises(PasswordTooLongError):
        hash_password(long_password)


def test_verify_password_rejects_over_length_password_without_error():
    hashed = hash_password("a" * 72)
    assert verify_password("a" * 73, hashed) is False
