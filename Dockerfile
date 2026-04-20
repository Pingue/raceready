# start by pulling the python image
FROM python:3.8-alpine

# copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# switch working directory
WORKDIR /app

# install the dependencies and packages in the requirements file
RUN pip install -r requirements.txt

RUN apk update && apk add git

# copy every content from the local file to the image
COPY . /app

# Create the default data directory so the DB is writable without a volume mount.
# Override the location at runtime with: -e DB_PATH=/your/path/db.sqlite3
# Mount a volume here for persistence:  -v /host/data:/app/data
RUN mkdir -p /app/data

VOLUME ["/app/data"]

# configure the container to run in an executed manner
ENTRYPOINT [ "python" ]

CMD ["raceready.py" ]

