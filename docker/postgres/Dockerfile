# Postgres with the legacy timezone names.
#
# Browsers in India report the timezone as "Asia/Calcutta" and Odoo saves that on the user.
# Debian 13 moved legacy names like it out of the default tzdata package, so without this
# Postgres fails with: time zone "Asia/Calcutta" not recognized, on any screen that groups
# dates (CRM pipeline, reports).
FROM postgres:15
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata-legacy \
    && rm -rf /var/lib/apt/lists/*
