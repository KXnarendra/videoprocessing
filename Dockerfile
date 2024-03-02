FROM python:3.10
COPY requirements.txt .
RUN pip install -r requirements.txt
ENV PYTHONUNBUFFERED=1
WORKDIR /usr/src/app/consumer
COPY __init__.py .
COPY src /usr/src/app/consumer/src
COPY config /usr/src/app/consumer/config
COPY consumer /usr/src/app/consumer/consumer

ENV PYTHONPATH "${PYTHONPATH}:/dvr"
RUN apt-get update
RUN apt-get install -y ffmpeg
RUN apt-get install -y libgl1-mesa-dev
RUN apt-get install inetutils-ping

CMD ["python" , "src/utils/utils.py"]