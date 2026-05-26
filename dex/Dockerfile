FROM ghcr.io/dexidp/dex:v2.41.1
COPY dex.yaml /etc/dex/config.template.yaml
EXPOSE 5556 5557
ENTRYPOINT ["/bin/sh", "-c", "sed \"s|\\$ISSUER|${ISSUER}|g\" /etc/dex/config.template.yaml > /etc/dex/config.docker.yaml && exec /usr/local/bin/dex serve /etc/dex/config.docker.yaml"]
