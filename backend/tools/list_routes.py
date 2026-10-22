"""Route inventory for manual inspection (`python3 -m tools.list_routes`)."""

from typing import Any

from app.main import app

HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def get_routes() -> list[tuple[str, str]]:
    """Return all registered API endpoints formatted as (methods_str, path)."""
    openapi_schema = app.openapi()
    paths: dict[str, Any] = openapi_schema.get("paths", {})
    if paths:
        results: list[tuple[str, str]] = []
        for path, operations in sorted(paths.items()):
            methods = [
                m.upper()
                for m in operations.keys()
                if m.upper() in HTTP_METHODS
            ]
            results.append((",".join(sorted(methods)), path))
        return results

    # Fallback: recursively traverse routes and IncludedRouter structures
    fallback_results: list[tuple[str, str]] = []
    for route in app.routes:
        orig_router: Any = getattr(route, "original_router", None)
        if orig_router is not None:
            ctx: Any = getattr(route, "include_context", None)
            prefix: str = str(getattr(ctx, "prefix", "") or "")
            for sub_route in getattr(orig_router, "routes", []):
                sub_methods = getattr(sub_route, "methods", None)
                sub_path = str(getattr(sub_route, "path", "") or "")
                if sub_methods:
                    method_str = ",".join(sorted(str(m) for m in sub_methods))
                    fallback_results.append((method_str, f"{prefix}{sub_path}"))
        else:
            route_methods = getattr(route, "methods", None)
            route_path = getattr(route, "path", None)
            if route_methods and route_path:
                method_str = ",".join(sorted(str(m) for m in route_methods))
                fallback_results.append((method_str, str(route_path)))
    return sorted(fallback_results, key=lambda r: r[1])


def main() -> None:
    for methods, path in get_routes():
        print(f"{methods:10s} {path}")


if __name__ == "__main__":
    main()
