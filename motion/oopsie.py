import os
import sentry_sdk

sentry_sdk.init(os.getenv("SENTRY_DSN", "http://f733377213d648a4af79f10b7ea86c3a@arm-control:8000/1"))

