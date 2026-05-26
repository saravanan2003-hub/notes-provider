FROM ghcr.io/dexidp/dex:v2.41.1

USER root

# Install Python3, pip, wget
RUN apk add --no-cache python3 py3-pip wget

# Install grpcurl
RUN wget -q -O /tmp/grpcurl.tar.gz \
      https://github.com/fullstorydev/grpcurl/releases/download/v1.9.1/grpcurl_1.9.1_linux_x86_64.tar.gz \
    && tar xz -C /usr/local/bin/ -f /tmp/grpcurl.tar.gz grpcurl \
    && rm /tmp/grpcurl.tar.gz

# Install Python deps in a venv to avoid system-package conflicts
COPY requirements-manage.txt /tmp/requirements-manage.txt
RUN python3 -m venv /opt/manage-venv \
    && /opt/manage-venv/bin/pip install --no-cache-dir -r /tmp/requirements-manage.txt

COPY dex.yaml /etc/dex/config.template.yaml
COPY manage.py /etc/dex/manage.py

EXPOSE 5556 5557

# 1. Render $ISSUER into config
# 2. Start Dex in background (HTTP:15556, gRPC:15557)
# 3. Start manage.py in foreground (port 5556) — proxies to Dex + exposes management API
ENTRYPOINT ["/bin/sh", "-c", "\
  sed \"s|\\$ISSUER|${ISSUER}|g\" /etc/dex/config.template.yaml > /etc/dex/config.docker.yaml && \
  /usr/local/bin/dex serve /etc/dex/config.docker.yaml & \
  sleep 3 && \
  /opt/manage-venv/bin/uvicorn manage:app --host 0.0.0.0 --port 5556 --app-dir /etc/dex \
"]
