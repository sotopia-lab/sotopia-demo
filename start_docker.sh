docker build -t sotopia/demo-ui .

docker run -p 8510:8501 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v ~/redis-data-sotopia-demo:/data \
  sotopia/demo-ui:latest