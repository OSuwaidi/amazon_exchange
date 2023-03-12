# بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ وبه نستعين

from flask import Flask, request, render_template, redirect, url_for, session
from flask_mysqldb import MySQL
from datetime import timedelta
import pandas as pd
import app_warns
import app_secrets
from datetime import date
from PIL import Image

app = Flask(__name__, static_url_path='/static')

app.config['MYSQL_HOST'] = app_secrets.mysql_host
app.config['MYSQL_USER'] = app_secrets.mysql_user
app.config['MYSQL_PASSWORD'] = app_secrets.mysql_pass
app.config['MYSQL_DB'] = app_secrets.mysql_db

mysql = MySQL(app)  # You can also use "with app.app_context():" to connect to a DB

app.secret_key = app_secrets.app_key
app.permanent_session_lifetime = timedelta(minutes=30)

abs_path = app_secrets.root_path
prod_path = "/static/images/"


with app.app_context():
    cursor = mysql.connection.cursor()

    cursor.execute("select * from users")
    columns = [col[0] for col in cursor.description]
    users_db = pd.DataFrame(cursor.fetchall(), columns=columns).set_index("email")

    cursor.execute("select * from products")
    columns = [col[0] for col in cursor.description]
    products_db = pd.DataFrame(cursor.fetchall(), columns=columns).set_index("owner")


def file_upload(req):
    global products_db
    img = req.files['img']
    img_name = img.filename
    img = Image.open(img).resize((224, 224))
    img.save(abs_path+prod_path+img_name)
    # img_data = np.frombuffer(img.read(), np.uint8)  # Convert "img.read()" (raw image data) from raw byte representation to 1D np.array
    # img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)  # Decode and convert 1D np.array into a 3D matrix (image)
    # img = cv2.resize(img, (224, 224))  # New size (width, height)
    values = [session["amazon_email"][:-10], *req.form.values(), prod_path+img_name, date.today()]  # Values must be placed in the same order of SQL table's columns
    query = f"insert into products values ({'%s, '*(len(values)-1)}%s)"
    with app.app_context():
        mysql.connection.autocommit(True)
        cursor = mysql.connection.cursor()
        cursor.execute(query, values)
    products_db = pd.concat([products_db, pd.DataFrame([values[1:]], index=[session["amazon_email"][:-10]], columns=columns[1:])])  # "products_db" columns
    session["posted_item"] = req.form["item_name"]


def file_delete(req, amazon_user):
    global products_db
    with app.app_context():
        mysql.connection.autocommit(True)
        cursor = mysql.connection.cursor()
        cursor.execute(f"""
            delete from products
            where owner='{amazon_user}' 
                and item_name='{req.form["deleted_item"]}';
        """)
    products_db = products_db[~((products_db.index == amazon_user) & (products_db["item_name"] == req.form["deleted_item"]))]
    session["deleted_item"] = req.form["deleted_item"]


@app.get('/test')
def tester():
    return render_template('test.html')


@app.get('/')
def home_page():
    return render_template('Homepage.html')


@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.post('/')
def home_login():
    if (amazon_email := request.form["amazon_email"]) in users_db.index:
        if users_db.loc[amazon_email, "password"] == request.form["password"]:
            session["amazon_email"] = amazon_email
            return redirect(url_for('market_page'))
        else:
            home_page = {"warning": app_warns.wrong_pass, "pass_red": "red"}
    else:
        home_page = {"warning": app_warns.acc_no_exist, "email_red": "red"}

    home_page.update(request.form)
    return render_template('Homepage.html', **home_page)


@app.get('/forget_pass')
def forget_page():
    return render_template('Forgot.html')


@app.post('/forget_pass')
def forget_send_link():
    print(request.form)
    if request.form["amazon_email"] in users_db.index:
        forget_pass = {"sent": True}
    else:
        forget_pass = {"warning": app_warns.acc_no_exist, "email_red": "red"}

    forget_pass.update(request.form)
    return render_template('Forgot.html', **forget_pass)


@app.get('/market')
def market_page():
    if amazon_email := session.get("amazon_email"):  # If successfully logged in...
        return render_template("Market.html",
                               users_db=users_db,
                               products_db=products_db,
                               amazon_email=amazon_email,
                               posted_item=session.pop("posted_item", None),
                               deleted_item=session.pop("deleted_item", None),)
    return redirect(request.referrer or '/')


@app.post('/market')
def market_post():
    if search_item := request.form.get("search_item"):
        products_db_filtered = products_db[products_db["item_name"].str.contains(search_item, case=False)]
        return render_template("Market.html",
                               users_db=users_db,
                               products_db=products_db_filtered,
                               amazon_email=session["amazon_email"],
                               search_item=search_item,)
    if "item_name" in request.form:
        file_upload(request)
    elif "deleted_item" in request.form:
        file_delete(request, session["amazon_email"][:-10])
    return redirect(url_for("market_page"))


@app.get('/market/<amazon_user>')
def user_products(amazon_user):
    if amazon_email := session.get("amazon_email"):
        if amazon_user in products_db.index:
            return render_template("MyProducts.html",
                                   amazon_user=amazon_user,
                                   amazon_email=amazon_email,
                                   products_db=products_db.loc[[amazon_user]],
                                   users_db=users_db,
                                   posted_item=session.pop("posted_item", None),
                                   deleted_item=session.pop("deleted_item", None))
        else:
            return render_template("NoProducts.html",
                                   amazon_user=amazon_user,
                                   amazon_email=amazon_email,
                                   posted_item=session.pop("posted_item", None),
                                   deleted_item=session.pop("deleted_item", None))

    return redirect(request.referrer or '/')


@app.post('/market/<amazon_user>')
def delete_product(amazon_user):
    if "item_name" in request.form:
        file_upload(request)
    elif "deleted_item" in request.form:
        file_delete(request, amazon_user)  # Only able to delete if "amazon_user" == "session['email'][:-10]"
    return redirect(url_for("user_products", amazon_user=amazon_user))


@app.get('/logout')
def logout():
    session.clear()
    return redirect(url_for("home_page"))


app.run(debug=True, host='0.0.0.0', port=3000)
