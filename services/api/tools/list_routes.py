"""Route inventory for manual inspection (`python3 -m tools.list_routes`)."""

from app.main import app


def main() -> None:
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if methods:
            print(f"{','.join(sorted(methods)):10s} {route.path}")


if __name__ == "__main__":
    main()
