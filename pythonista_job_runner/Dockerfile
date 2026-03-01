ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache cpulimit curl zip

WORKDIR /app
COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh
RUN addgroup -S pjr && adduser -S -G pjr pjr && chown -R pjr:pjr /app /run.sh
USER pjr

CMD [ "/run.sh" ]

