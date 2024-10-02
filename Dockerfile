FROM python:slim
RUN --mount=source=dist,target=/dist pip install --no-cache /dist/*.whl
CMD [ "python", "-m", "kumaprobe" ]
