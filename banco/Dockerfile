FROM python:3.11-slim-buster

COPY . /bank    

WORKDIR /bank

RUN pip install -r requirements.txt

CMD ["python","Bank.py"]