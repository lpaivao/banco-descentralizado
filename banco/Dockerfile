FROM python:3.11-alpine

COPY . /bank    

WORKDIR /bank

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python","Bank.py"]