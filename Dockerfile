# Define the image to build from
FROM python:3.11-slim

# Create app directory
WORKDIR /usr/src/app

# Install app dependencies
#   NOTE: requirements.txt is copied first so the layer caches independently
#   of the application source.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bundle app source
COPY . .

# Bind to $port
EXPOSE $port

# Run the app
# i.e. `python _index.py`
CMD [ "python", "_index.py" ]

# Confirm the Docker image was created:
# docker images

# docker network create api
# docker ps
# docker network inspect api
# docker logs <ContainerID>
# docker exec -it <ContainerID> /bin/bash
# docker exec -it <ContainerID> curl -X GET http://localhost:3000/
