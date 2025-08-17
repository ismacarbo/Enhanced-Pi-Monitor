from functools import wraps
from flask import session, redirect, url_for
import jwt
from config import SECRET_KEY

def token_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = session.get('jwt')
        if not token:
            return redirect(url_for('login'))
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user = data['username']
        except Exception:
            return redirect(url_for('login'))
        return f(user, *args, **kwargs)
    return wrapped
