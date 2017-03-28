from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    # query user's stock information
    first_select = db.execute("SELECT id, symbol, SUM(shares) FROM stock_history WHERE id=:id GROUP BY symbol ORDER BY symbol", id=session["user_id"])
    user_portfolio = list()
    
    # filter out zero shares for not showing in index page
    for stock in first_select:
        # check sum of shares are not zero, if not append dict into user_portfolio
        if stock["SUM(shares)"] == 0:
            continue
        else:
            quote = lookup(stock["symbol"])
            user_portfolio.append({"symbol":stock["symbol"], "name":quote["name"], "SUM(shares)":stock["SUM(shares)"], "price":quote["price"]})
    
    # calculate (stock price * shares ) current price not history price
    for stock in user_portfolio:
        stock["total"] = round(stock["price"] * stock["SUM(shares)"], 2)
    
    # calculate total portfolio
    total_stock = 0
    for stock in user_portfolio:
        total_stock += stock["total"] 
    
    remainder = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    
    return render_template("index.html", stocks=user_portfolio, cash_remainder=round(remainder[0]["cash"], 2), total_portfolio=round(total_stock + remainder[0]["cash"], 2))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure symbol and shares not blank
        if not request.form.get("symbol"):
            return apology("missing symbol")
        
        if not request.form.get("shares"):
            return apology("missing shares")
            
        # check symbol valid 
        quoted = lookup(request.form.get("symbol"))
        if not quoted:
            return apology("invalid symbol")
        
        # check shares is valid
        try:
            input_shares = int(request.form.get("shares"))
            if input_shares > 0:
                pass
            else:
                return apology("invalid shares")
        except:
            return apology("invalid shares")
        
        # query user's cash
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        current_cash=rows[0]["cash"]
        
        # check cash enought for stock
        buying_require = quoted["price"] * input_shares
        if current_cash < buying_require:
            return apology("can't afford")
        else:
            # insert buying into table stock_history
            db.execute("INSERT INTO stock_history (id, symbol, price, shares, transacted) VALUES (:id, :symbol, :price, :shares, :transacted)",
                        id=session["user_id"], symbol=quoted["symbol"], price=quoted["price"], shares=input_shares, transacted=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # update cash in user TABLE
            db.execute("UPDATE users SET cash = cash - :buying_cash WHERE id=:id", buying_cash=buying_require, id=session["user_id"])
            
        return redirect(url_for("index"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)    
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    stock_history = db.execute("SELECT symbol, shares, price, transacted FROM stock_history WHERE id=:id", id=session["user_id"])
    return render_template("history.html", stocks=stock_history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        
        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""
    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
         # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol")
        
        # check symbol is valid
        quoted = lookup(request.form.get("symbol"))
        if not quoted:
            return apology("invalid symbol")
        
        # display stock information
        return render_template("quoted.html", name=quoted["name"], symbol=quoted["symbol"], price=quoted["price"] )
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # forget any user_id
    session.clear()
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")
        
        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        
        # make sure password and confirmation match
        if request.form.get("password") != request.form.get("password_confirm"):
            return apology("password not match")
            
        # check user name is only one
        exist = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(exist):
            return apology("username taken")
        else:
            # insert user name and password into database
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=pwd_context.hash(request.form.get("password")))
            
        # store id in session
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(rows) == 0:
            return apology("{}".format(request.form.get("username")))
        session["user_id"] = rows[0]["id"]
        
        # once register successfully, log in automatically
        return redirect(url_for("index"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure symbol and shares not blank
        if not request.form.get("symbol"):
            return apology("missing symbol")
        
        if not request.form.get("shares"):
            return apology("missing shares")
        
        # check shares is positive integer
        try:
            input_shares = int(request.form.get("shares"))
            if input_shares > 0:
                pass
            else:
                return apology("invalid shares")
        except:
            return apology("invalid shares")
            
        # query stock_history to get user symbol and shares
        user_portfolio = db.execute("SELECT id, symbol, SUM(shares) FROM stock_history WHERE id=:id GROUP BY symbol ORDER BY symbol", id=session["user_id"])
        
        user_stock_dict = dict()
        
        for stock in user_portfolio:
            user_stock_dict[stock["symbol"]] = stock["SUM(shares)"]
        
        # check symbol want to sell is valid
        symbol_sell = request.form.get("symbol").upper()
        if symbol_sell in user_stock_dict.keys():
            pass
        else:
            return apology("symbol not owned 1")
            
        # check shares are enough for sell
        
        if user_stock_dict[symbol_sell] == 0:
            return apology("symbol not owned 2")
        elif input_shares > user_stock_dict[symbol_sell]:
            return apology("too many shares")
        
        # insert sell info into stock_history
        quoted = lookup(symbol_sell)
        db.execute("INSERT INTO stock_history (id, symbol, price, shares, transacted) VALUES (:id, :symbol, :price, :shares, :transacted)",
                    id=session["user_id"], symbol=symbol_sell, price=quoted["price"], shares=(-input_shares), transacted=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # update cash in users
        selling_cash = input_shares * quoted["price"]
        db.execute("UPDATE users SET cash = cash + :selling_cash WHERE id=:id", selling_cash = selling_cash, id=session["user_id"])
        
        # sell successful then return index
        return redirect(url_for("index"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")
