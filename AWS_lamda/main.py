import random

import sys
import os
import time
import xgboost as xgb
import yfinance as yf
import pandas as pd
import numpy as np
import os
import math
import time

import json
import sys
# import struct
import jwt
from jwt import PyJWTError
from datetime import datetime,timedelta
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
from passlib.context import CryptContext
from sklearn.model_selection import train_test_split

from secrets import *





fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

SECRET_KEY = Key
ALGORITHM = algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
pwd_context = CryptContext(schemes=['bcrypt'],deprecated="auto")

class User(BaseModel):
    username: str
    email: str = None 
    full_name: str = None 
    disabled: bool = None 

class UserInDB(User):
    hashed_password: str

class TokenData(BaseModel):
    username: str = None

class Token(BaseModel):
    access_token: str
    token_type: str

def verify_password(plain_password,hashed_password):
    return pwd_context.verify(plain_password,hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def fake_hash_password(password: str):
    return "fakehashed" + password

def get_user(db,username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(fake_db,username:str,password:str):
    user = get_user(fake_db,username)
    if not user:
        return False
    if not verify_password(password,user.hashed_password):
        return False
    return user

def create_access_token(*,data:dict,expires_delta:timedelta=None):
    to_encode = data.copy()
    if expires_delta:
        expires = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({'exp':expire})
    encoded_jwt = jwt.encode((to_encode, SECRET_KEY,ALGORITHM))
    return encoded_jwt

async def get_current_user(token:str=Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate':"Bearer"},
    )
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except PyJWTError:
        raise credentials_exception
    user = get_user(fake_users_db,username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400,detail="Inactive user")
    return current_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username,form_data.password)
    if not user:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Incorret username or password',
        headers={"WWW-Authenticate":"Bearer"},
    )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={'sub':user.username},expires_delta=access_toekn_expires
    )
    return {"access_token":access_token,"token_type":"bearer"}


@app.get("/users/me/",response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/users/me/items/")
async def read_own_items(current_user: User = Depends(get_current_active_user)):
    return [{'item_id':"Foo","owner":current_user.username}]

##############################################


from sqlalchemy import create_engine

engine = create_engine('sqlite:///mydb.db',echo=False)
try:
    db = pd.DataFrame({'number':[],'label1':[],'label2':[]}).to_sql('csv',con=engine,if_exists='fail',index=False)
except ValueError:
    print("database already created")
    pass

class payload(BaseModel):
    number: list = None
    label1: list = None
    label2: list = None
    
  

@app.post("/data/")
async def read_data(data: payload, request:Request):
    data_frame = pd.DataFrame()
    client_host = request.client.host
    data = dict(data)
    print(data['number'][0])
    current_table = pd.read_sql("SELECT number FROM csv",con=engine)
    print(current_table)
    if data['number'][0] in [number for number in current_table.number]:
        # print('data already processed') 
        raise HTTPException(status_code=404,detail='data already processed')
    
    prev_data = pd.read_sql("SELECT * FROM csv",con=engine)
    data = pd.DataFrame(data)
    prev_data = prev_data.append(data,ignore_index=True)
    print(prev_data)
    prev_data.to_sql('csv',con=engine,if_exists='replace',index=False)
   
    return {'client_host':client_host,"data":{}}

@app.post('/update/')
async def update_data(data:payload,request:Request):
    client_host = request.client.host
    data = dict(data)
    print(data)
    
    current_table = pd.read_sql("""SELECT * FROM csv""",con=engine)
    if data['number'][0] not in [number for number in current_table.number]:
        raise HTTPException(status_code=404,detail='data not entered yet')

    current_table.loc[current_table.number == int(data['number'][0]),'label1'] = data['label1']
    current_table.loc[current_table.number == int(data['number'][0]),'label2'] = data['label2']
    print(current_table)
    current_table.to_sql('csv',con=engine,if_exists='replace',index=False)

    return {'client_host':client_host,'data':{}}

@app.post('/delete/')
async def delete(data:payload, request:Request):
    client_host = request.client.host
    data = dict(data)

    current_table = pd.read_sql("SELECT * FROM csv",con=engine)
    current_table = current_table[current_table.number != int(data['number'][0])]
    print(current_table)
    current_table.to_sql('csv',con=engine,if_exists='replace',index=False)

    return {'client_host':client_host,'data':{}}


@app.get('/read_sql/')
async def read_sql():
    df = pd.read_sql('csv',con=engine)
    print(df)
    return {'query':df.to_dict()}

@app.post("/feed_data/")
async def feed_data(request:Request):  
    print(pd.read_sql("SELECT * FROM csv",con=engine).to_dict(orient='list'))
    return {'data so far':pd.read_sql("SELECT * FROM csv",con=engine).to_dict(orient='list')}

@app.get("/")
async def root():
    used = []
    digit = random.choice(range(1000,100000))#sys.maxsize
    if digit not in used:
        used.append(digit)
        return {"message": digit}
    elif digit in used:
        return {"message":'this is a used digit'}

@app.post("/prediction/{stock_id}")
async def predict(stock_id,token: str = Depends(oauth2_scheme)):
    loaded_model = xgb.Booster()
    loaded_model.load_model('xgbregression.model')
    stock = yf.Ticker(str(stock_id))
    history = stock.history(period='max')
    stock_changes = history.pct_change()
    
    stock_changes.drop(stock_changes.index[0],inplace=True)
    stock_changes = pd.concat([stock_changes.Close.shift(-i) for i in range(100)],axis=1)
    stock_changes.drop(stock_changes.index[-100:],inplace=True)
    stock_changes.columns = [ f'Days_{i}'for i in range(len(stock_changes.columns))]

    X = stock_changes.loc[:,"Days_1":]
    y = stock_changes.loc[:,'Days_0']
    X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.2,random_state=0)
    
    dtrain = xgb.DMatrix(X_train,label=y_train,nthread=-1)
    dtest = xgb.DMatrix(X_test,label=y_test,nthread=-1)
    prediction = loaded_model.predict(dtest)
    prediction = pd.DataFrame(prediction).to_dict()
    
    return {"prediction":prediction}

@app.post("/TONY's/stock/{stock_id}")
async def read_items(stock_id,token: str = Depends(oauth2_scheme)):
    stock = yf.Ticker(str(stock_id))
    stock_info = stock.info
    history = stock.history(period='max').to_dict()

    return {"stock":stock_info,
            "history":history}


############
import alpaca_trade_api as tradeapi

api_key = api_key
api_secret = api_secret
base_url = base_url

@app.post("/alpaca/{stock_id_list}/{timeframe}")
async def barrs(stock_id_list,timeframe,limit = 20):#token: str = Depends(oauth2_scheme)):
    api = tradeapi.REST(api_key,api_secret,base_url,api_version='v2')
    account = api.get_account()

    stock_id_list = stock_id_list.replace(">","").split("<")
    stock_id_list = [i.upper() for i in stock_id_list]

    if len(stock_id_list[1:]) > int(limit):
        return {"Query_Limit":"Exceeded Query Limit"}

    data = dict()
    for stock in stock_id_list[1:]:      
        try:
            bar = api.get_barset(stock,timeframe,limit=2)
            STD = (bar[stock][1].c - bar[stock][0].c)/ bar[stock][1].c
        except IndexError as e:
            return {"Query Error":"one of your queried stocks does not exist"}
        except Exception as e:
            return {"Timeframe Error":{"please choose":{'minute','1Min','5Min','15Min','day','1D'}}}
            
        data[stock] = dict()
        data[stock]["ID"] = stock
        data[stock]["SDT"] = STD
        data[stock]["Price_Now"] = bar[stock][-1].c

    return data