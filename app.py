import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol, name, price, SUM(shares) AS totalShares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?" , user_id)[0]["cash"]
    total = cash

    for stock in stocks:
        total += stock["price"] * stock["totalShares"]

    return render_template("index.html", stocks=stocks, cash=cash, usd=usd , total=total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol").upper()
        stock = lookup(symbol.upper())

        if not symbol:
            return apology("Symbol field can not be left blank.")
        elif not stock:
            return apology("Please enter a valid stock.")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares should be an positive integer.")
        if shares <= 0:
            return apology("Trade not allowed")

        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)[0]["cash"]

        stock_name = stock["name"]
        stock_price = stock["price"]
        total_price = stock_price * shares
        if user_cash < total_price:
            return apology("You Don't have enough money.")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash - total_price, user_id)
            date_time = datetime.datetime.now()
            db.execute("INSERT INTO transactions(user_id, name, shares, price, type, symbol, time) VALUES(?, ?, ?, ?, ?, ?, ?)", user_id, stock_name, shares, stock_price, 'Buy', symbol, date_time)
            flash("Transaction Completed Successfully!")
            return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transaction_db = db.execute("SELECT * FROM transactions WHERE user_id = :id", id = user_id)
    return render_template("history.html" , transactions = transaction_db)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Symbol field can not be left blank.")
        stock = lookup(symbol.upper())

        if stock == None:
            return apology("This Stock does not exist.")
        else:
            return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_pass = request.form.get("confirmation")
        if (len(username) == 0):
            return apology("Username field can not be left blank.")
        if (len(password) == 0):
            return apology("Password field can not be left blank.")
        if (len(confirm_pass) == 0):
            return apology("Confirm Password field can not be left blank.")
        if password != confirm_pass:
            return apology("Passwords do not match.")
        hash = generate_password_hash(password)

        try:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)
        except:
            return apology("Username already exist.")
        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        symbols_user = db.execute("SELECT symbol FROM transactions WHERE user_id = :id GROUP BY symbol HAVING SUM(shares) > 0", id=user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in symbols_user])
    else:
        symbol = request.form.get("symbol").upper()
        stock = lookup(symbol.upper())

        if not symbol:
            return apology("Symbol field can not be left blank.")
        elif not stock:
            return apology("Please enter a valid stock.")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Shares should be an positive integer.")
        if shares <= 0:
            return apology("Trade not allowed")

        user_id = session["user_id"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)[0]["cash"]

        users_share = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY shares", user_id, symbol)[0]["shares"]

        if users_share < shares:
            return apology("Not Enough share to sell in your account.")

        stock_name = stock["name"]
        stock_price = stock["price"]
        total_price = stock_price * shares

        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + total_price, user_id)
        date_time = datetime.datetime.now()
        db.execute("INSERT INTO transactions(user_id, name, shares, price, type, symbol, time) VALUES(?, ?, ?, ?, ?, ?, ?)", user_id, stock_name, -shares, stock_price, 'Sell', symbol, date_time)
        flash("Transaction Completed Successfully!")
        return redirect("/")
