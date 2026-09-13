FROM python:3.12-slim

# Bump this when a newer gpth release is desired -- asset filenames embed
# the version, so this can't be resolved dynamically via a stable "latest" URL.
ARG GPTH_VERSION=6.2.1
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) GPTH_ARCH=x64 ;; \
        arm64) GPTH_ARCH=arm64 ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /usr/local/bin/gpth \
      "https://github.com/Xentraxx/GooglePhotosTakeoutHelper_Neo/releases/download/v${GPTH_VERSION}/gpth_neo-${GPTH_VERSION}-release-linux-${GPTH_ARCH}.bin"; \
    chmod +x /usr/local/bin/gpth

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

ENTRYPOINT ["python", "-m", "app.main"]
