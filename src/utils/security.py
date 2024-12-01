import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import jwt

logger = logging.getLogger(__name__)

class SecurityManager:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def generate_token(self, data: Dict[str, Any], expires_in: int = 3600) -> str:
        try:
            exp = datetime.utcnow() + timedelta(seconds=expires_in)
            payload = {
                **data,
                'exp': exp
            }
            return jwt.encode(payload, self.secret_key, algorithm='HS256')
        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            raise

    def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()