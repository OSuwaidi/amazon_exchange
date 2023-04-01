# بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ وبه نستعين

from flask import Flask, request, render_template, redirect, url_for, session
from flask_mysqldb import MySQL
from datetime import timedelta
import pandas as pd
import app_secrets
from datetime import date
from PIL import Image
from secrets import compare_digest

app = Flask(__name__, static_url_path='/static')

app.config['MYSQL_HOST'] = app_secrets.mysql_host
app.config['MYSQL_USER'] = app_secrets.mysql_user
app.config['MYSQL_PASSWORD'] = app_secrets.mysql_pass
app.config['MYSQL_DB'] = app_secrets.mysql_db

mysql = MySQL(app)

app.secret_key = app_secrets.app_key
app.permanent_session_lifetime = timedelta(minutes=30)

abs_path = app_secrets.root_path
prod_path = "/static/images/"


with app.app_context():
    cursor = mysql.connection.cursor()

    cursor.execute("select * from users")  # "cursor.fetchall()" after the "select" statement returns a tuple of rows as tuples
    columns = [col[0] for col in cursor.description]
    users_db = pd.DataFrame(cursor.fetchall(), columns=columns).set_index("email")

    cursor.execute("select * from products")
    columns = [col[0] for col in cursor.description]
    products_db = pd.DataFrame(cursor.fetchall(), columns=columns).set_index("owner")


def file_upload(req):
    global products_db
    # img_data = np.frombuffer(img.read(), np.uint8)  # Convert "img.read()" (raw image data) from raw byte representation to 1D np.array
    # img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)  # Decode and convert 1D np.array into a 3D matrix (image)
    # img = cv2.resize(img, (224, 224))  # New size (width, height)
    img = req.files['img']
    img_name = img.filename
    img = Image.open(img).resize((224, 224))
    img.save(abs_path+prod_path+img_name)
    values = [session["amazon_email"][:-10], *req.form.values(), prod_path+img_name, date.today()]  # Values must be placed in the same order of SQL table's columns
    query = f"insert into products values ({'%s, '*(len(values)-1)}%s)"
    with app.app_context():
        mysql.connection.autocommit(True)
        cursor = mysql.connection.cursor()
        cursor.execute(query, values)
    products_db = pd.concat([products_db, pd.DataFrame([values[1:]], index=[session["amazon_email"][:-10]], columns=columns[1:])])  # "columns[1:]" is "products_db" columns
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


@app.after_request
def add_header(response):
    # An attempt to prevent browsers from caching pages such that upon logout, user can't access previous page by pressing "previous page" button
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.get('/')
def home_page():
    return render_template('Homepage.html')


@app.post('/')
def home_login():
    if (amazon_email := request.form["amazon_email"]) in users_db.index:
        if compare_digest(users_db.loc[amazon_email, "password"], request.form["password"]):
            session["amazon_email"] = amazon_email
            return redirect(url_for('market_page'))
        else:
            session["wrong_pass"] = True
    else:
        session["wrong_email"] = True

    return render_template('Homepage.html', **session, **request.form)


@app.get('/forget_pass')
def forget_page():
    return render_template('Forgot.html')


@app.post('/forget_pass')
def forget_send_link():
    if request.form["amazon_email"] in users_db.index:
        session["sent"] = True
    else:
        session["no_email"] = True

    return render_template('Forgot.html', **session, **request.form)


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
    if request.form.get("item_name"):
        file_upload(request)
    elif request.form.get("deleted_item"):
        file_delete(request, session["amazon_email"][:-10])
    elif item_name := request.form.get("edited_item"):
        pass
    return redirect(url_for("market_page"))


@app.get('/market/<amazon_user>')
def user_products(amazon_user):
    if amazon_email := session.get("amazon_email"):
        if amazon_user in products_db.index:
            has_products = True
            products_db_filtered = products_db.loc[[amazon_user]]
        else:
            has_products = False
            products_db_filtered = None

        return render_template("MyProducts.html",
                               amazon_user=amazon_user,
                               amazon_email=amazon_email,
                               products_db=products_db_filtered,
                               users_db=users_db,
                               posted_item=session.pop("posted_item", None),
                               deleted_item=session.pop("deleted_item", None),
                               has_products=has_products)

    return redirect(request.referrer or '/')


@app.post('/market/<amazon_user>')
def delete_product(amazon_user):
    if request.form.get("item_name"):
        file_upload(request)
    elif request.form.get("deleted_item"):
        file_delete(request, amazon_user)  # Only able to delete if "amazon_user" == "session['email'][:-10]"
    return redirect(url_for("user_products", amazon_user=amazon_user))


@app.get('/logout')
def logout():
    session.clear()
    return redirect(url_for("home_page"))


app.run(debug=True, host='0.0.0.0', port=3000)
