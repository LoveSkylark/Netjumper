FROM python:3.12-slim

WORKDIR /workspace

RUN pip install --no-cache-dir \
    requests \
    urllib3 \
    certifi \
    python-hosts \
    python-dotenv \
    typing-extensions \
    pyyaml \
    pynetbox \
    fuzzysearch

ENV PYTHONPATH=/workspace:/scripts

CMD ["tail", "-f", "/dev/null"]
