import os

from antientropy_mcp.server import AUTH_TOKEN, BearerAuthMiddleware, mcp

TRANSPORT = os.environ.get("TRANSPORT", "stdio")

if TRANSPORT == "stdio":
    mcp.run(transport="stdio")
else:
    import uvicorn

    app = mcp.streamable_http_app()

    if AUTH_TOKEN:
        app = BearerAuthMiddleware(app, AUTH_TOKEN)

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host=host, port=port)
