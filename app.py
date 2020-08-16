import os
import yfinance as yf
import urllib
import asyncio
import logging
from flask import Flask, render_template, request, session, redirect, url_for
from flask_pymongo import PyMongo

MONGO_URI = os.getenv('MONGO_URI')

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://carlvinggaard:18M0n90d603@cluster0-lqr5z.mongodb.net/stockTradingGame?retryWrites=true&w=majority"
app.secret_key = "secretkey"
mongo = PyMongo(app)

# FUNCTIONS
def get_stock_data():
  stockCodeArray = []
  stocks = mongo.db.stocks.find()

  for stock in stocks:
    stockCodeArray.append(stock['stockCode'])
  
  # Get data from API
  data = yf.download(stockCodeArray, period="1d")

  get_stock_tuple = lambda code: (code, round(data[("Close", code)][0], 2))

  stockPriceDict = dict(map(get_stock_tuple, stockCodeArray))

  return stockPriceDict

def get_stock_price(stockCode):
  data = yf.download(stockCode, period="d1")
  return round(data["Close"][0], 2)

def get_total_value(username):
  user = mongo.db.users.find_one({ 'username': username })
  data = get_stock_data()

  get_stock_value = lambda stock: stock['quantity'] * data[stock['stockCode']]

  return round(sum(list(map(get_stock_value, user['portfolio']))), 2)

def is_valid_purchase(quantity, price, cash):
  return quantity * price < cash

def is_valid_sale(quantity, stockQuantity):
  return stockQuantity > quantity

def buy_stock(stockCode, quantity, price):
  # If there is no object with this stock code in the portfolio, create one
  mongo.db.users.update({ 'username': session['username'], 'portfolio.stockCode': { '$ne': stockCode } }, { '$push': { 'portfolio': { 'stockCode': stockCode, 'quantity': 0 } } })
 
  # Increment the portfolio with <quantity>
  query = { 'username': session['username'], 'portfolio.stockCode': stockCode }
  value = { '$inc': { 'portfolio.$.quantity': quantity } }
  mongo.db.users.update_one(query, value)

  # Subtract the cash
  mongo.db.users.update({ 'username': session['username']}, { '$inc': { 'cash': -(quantity * price) } })

def sell_stock(stockCode, quantity, price):
  # Decrement the portfolio with <quantity>
  query = { 'username': session['username'], 'portfolio.stockCode': stockCode }
  value = { '$inc': { 'portfolio.$.quantity': -quantity } }
  mongo.db.users.update_one(query, value)

  # Add the cash
  mongo.db.users.update({ 'username': session['username']}, { '$inc': { 'cash': quantity * price } })

def create_user(username):
  mongo.db.users.insert({ 'username': username, 'cash': 20000.00 })
  return 


# ROUTES
@app.route('/', methods=['POST', 'GET'])
def index():
  if 'username' in session:
    return render_template('portfolio.html', data=get_stock_data(), user=mongo.db.users.find_one({ 'username': session['username'] }), value=get_total_value(session['username']))
  else:
    if request.method == 'POST':
      username = request.form['username'].lower()
      session['username'] = username
      exists = mongo.db.users.find_one({ 'username': username })
      if not exists:
        create_user(username)
      return redirect(url_for('index'))
    return render_template('frontpage.html')

@app.route('/history')
def history():
  if 'username' in session:
    return render_template('history.html', user=mongo.db.users.find_one({ 'username': session['username'] }))
  else:
    return redirect(url_for('index'))

@app.route('/trade')
def trade():
  if 'username' in session:
    return render_template('trade.html', data=get_stock_data(), user=mongo.db.users.find_one({ 'username': session['username']}))
  else:
    return redirect(url_for('index'))
  
@app.route('/buy/<stockCode>', methods=['GET', 'POST'])
def buy(stockCode):
  user = mongo.db.users.find_one({ 'username': session['username']})
  price = get_stock_price(stockCode)
  total = 0
  quantity = 0
  error = ''
  if request.method == "POST":
    quantity = int(request.form["quantity"])
    total = quantity * price
    if 'buy' in request.form:
      if is_valid_purchase(quantity, price, user['cash']):
        buy_stock(stockCode, quantity, price)
        return redirect(url_for('index'))
      else:
        error = "You don't have enough money for that."
  return render_template('buy.html', user=user, stock=stockCode, price=price, total=total, quantity=quantity, error=error)

@app.route('/sell/<stockCode>', methods=['GET', 'POST'])
def sell(stockCode):
  user = mongo.db.users.find_one({ 'username': session['username'] })
  stockQuantity = [stock['quantity'] for stock in user['portfolio'] if stock['stockCode'] == stockCode][0]
  price = get_stock_price(stockCode)
  total = 0
  quantity = 0
  error = ''
  if request.method == "POST":
    quantity = int(request.form["quantity"])
    total = quantity * price
    if 'sell' in request.form:
      if is_valid_sale(quantity, stockQuantity):
        sell_stock(stockCode, quantity, price)
        return redirect(url_for('index'))
      else:
        error = "You don't have that much of this stock."
  return render_template('sell.html', user=user, stock=stockCode, price=price, total=total, quantity=quantity, error=error, stockQuantity=stockQuantity)

@app.route('/logout')
def logout():
  session.pop('username', None)
  return redirect(url_for('index'))

@app.route('/stocks')
def stocks_page():
  return render_template('stocks.html', data=get_stock_data())