FROM redis/redis-stack:latest

# Set working directory
WORKDIR /app

# Install git and other dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python
# Clone repositories
RUN git clone https://github.com/sotopia-lab/sotopia.git && \
    git clone https://github.com/sotopia-lab/sotopia-demo.git

# Setup sotopia
RUN cd /app/sotopia && git checkout feature/sotopia-ui-fastapi-websocket && pip install -e .

# Setup sotopia-demo
RUN cd /app/sotopia-demo && git checkout feature/sotopia-demo-with-api

# Install additional dependencies
RUN pip install streamlit redis-om fastapi uvicorn websockets

ENV REDIS_OM_URL="redis://localhost:6379"
ENV OPENAI_API_KEY=$OPENAI_API_KEY

# Only expose Streamlit port
EXPOSE 8501

RUN echo '#!/bin/bash\n\
# Wait for Redis to be ready\n\
while ! redis-cli ping; do\n\
  echo "Waiting for Redis..."\n\
  sleep 1\n\
done\n\
cd /app/sotopia && nohup python sotopia/ui/fastapi_server.py > /app/api.log 2>&1 &' > /app/run_api.sh && \
    chmod +x /app/run_api.sh

# Final command to run all services
CMD redis-stack-server --dir /data --port 6379 & \
    sleep 5 && \
    /app/run_api.sh && \
    cd /app/sotopia-demo && streamlit run app.py --server.port 8501 --server.address 0.0.0.0


# # Set the entry point
# ENTRYPOINT ["/app/start.sh"]