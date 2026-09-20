from slowapi import Limiter
from slowapi.util import get_remote_address

# Single Limiter instance for the app
limiter = Limiter(key_func=get_remote_address)
