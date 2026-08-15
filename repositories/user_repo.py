from services import database

# Fields that must never cross from a DB row into an API response model.
CREDENTIAL_FIELDS = frozenset({"password_hash"})


def public_user_fields(row: dict) -> dict:
    """Project credential fields out of a user row before it reaches the API layer."""
    return {key: value for key, value in row.items() if key not in CREDENTIAL_FIELDS}


class UserRepository:
    def create_user(self, email: str, password_hash:str, display_name: str) -> int:
        """Create a new user and return the user ID."""
        return database.create_user(email.strip().lower(), password_hash, display_name)

    def get_user_by_email(self, email: str) -> dict | None:
        """Retrieve a user by email. Returns None if not found."""
        return database.get_user_by_email(email.strip().lower())

    def get_user_by_id(self, user_id: int) -> dict | None:
        """Retrieve a user by ID. Returns None if not found."""
        return database.get_user_by_id(user_id)