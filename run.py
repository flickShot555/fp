"""Convenience runner for the FreightPower AI API."""

import uvicorn

from apps.api.settings import settings


def main():
    uvicorn.run(
        "apps.api.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
