ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    cpulimit=0.2-r3 \
    curl=8.14.1-r2 \
    zip=3.0-r13

# Create a non-root user for running submitted jobs
RUN addgroup -S jobrunner && adduser -S -G jobrunner -h /home/jobrunner jobrunner

WORKDIR /app
COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8787/health || exit 1

CMD [ "/run.sh" ]
