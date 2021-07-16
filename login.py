from flask import redirect, session
from functools import  wraps


def is_logged_in(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'logged_in' in session:
            return func(*args, **kwargs)
        else:
            return redirect('/login')

    return wrapper
