
pyenv install 3.11

pyenv local 3.11

pyenv exec python -v

pyenv exec python -m venv .venv

#source .venv/bin/activate # mac/linux
.venv\Scripts\activate

pip install -r requirements.txt

uvicorn storeapi.main:app --reload