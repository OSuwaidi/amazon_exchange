# بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ وبه نستعين

from flask import Flask, request, render_template, redirect, url_for, session
from flask_mysqldb import MySQL
from functools import wraps
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

mysql = MySQL(app)  # Establish the connection to the MySQL DB

app.secret_key = app_secrets.app_key
app.permanent_session_lifetime = timedelta(minutes=30)

abs_path = app_secrets.root_path
prod_path = "/static/images/"

# Retrieve all "users" and "products" data tables from the MySQL database hosted on the cloud:
with app.app_context():
    cursor = mysql.connection.cursor()  # Create a cursor against the connection

    cursor.execute("select * from users")
    columns = [col[0] for col in cursor.description]
    # "cursor.fetchall()" returns the resulting query/execution as a tuple of tupled rows/records
    users_db = pd.DataFrame(cursor.fetchall(), columns=columns).set_index("email")

    cursor.execute("select * from products")
    columns = [col[0] for col in cursor.description]
    products_db = pd.DataFrame(cursor.fetchall(), columns=columns).set_index("owner")
    cursor.close()


def file_upload(item_name, req, amazon_user):
    global products_db
    # img_data = np.frombuffer(img.read(), np.uint8)  # Convert "img.read()" (raw image data) from raw byte representation to 1D np.array
    # img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)  # Decode and convert 1D np.array into a 3D matrix (image)
    # img = cv2.resize(img, (224, 224))  # New size (width, height)
    img = req.files['img']
    img_name = img.filename
    img = Image.open(img).resize((224, 224))
    img.save(abs_path+prod_path+img_name)
    form = req.form.copy()
    is_IT = form.pop("is_IT", None) is not None
    values = [amazon_user, *form.values(), is_IT, prod_path+img_name, date.today()]  # Values must be placed in the same order of SQL table's columns
    query = f"insert into products values ({'%s, '*(len(values)-1)}%s)"
    with app.app_context():
        mysql.connection.autocommit(True)
        cursor = mysql.connection.cursor()
        cursor.execute(query, values)
    # "columns[1:]" is "products_db"'s columns
    products_db = pd.concat([products_db, pd.DataFrame([values[1:]], index=[amazon_user], columns=columns[1:])])
    session["posted_item"] = item_name


def file_delete(item_name, amazon_user):
    global products_db
    with app.app_context():
        mysql.connection.autocommit(True)
        cursor = mysql.connection.cursor()
        cursor.execute(f"""
            delete from products
            where owner='{amazon_user}' 
                and item_name='{item_name}';
        """)
    products_db = products_db[~((products_db.index == amazon_user) & (products_db["item_name"] == item_name))]
    session["deleted_item"] = item_name


def check_modification(req, amazon_user):
    if item_name := req.form.get("posted_item"):
        file_upload(item_name, req, amazon_user)
    elif item_name := req.form.get("deleted_item"):
        file_delete(item_name, amazon_user)
    elif item_name := req.form.get("edited_item"):
        # To be added later
        pass


def login_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if "amazon_email" in session:
            return route(*args, **kwargs)
        else:
            return redirect(request.referrer or '/')
    return wrapper


@app.after_request
def add_header(response):
    # An attempt to prevent browsers from caching pages such that upon logout, user can't access previous page by pressing "previous page" button
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.get('/test')
def test_page():
    return render_template("test.html")


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

    return render_template('Homepage.html', **request.form)


@app.get('/forget_pass')
def forget_page():
    return render_template('Forgot.html')


@app.post('/forget_pass')
def forget_send_link():
    if request.form["amazon_email"] in users_db.index:
        session["sent"] = True
    else:
        session["no_email"] = True

    return render_template('Forgot.html', **request.form)


@app.get('/market')
@login_required
def market_page():
    return render_template("Market.html",
                           users_db=users_db,
                           products_db=products_db,
                           amazon_email=session["amazon_email"],
                           posted_item=session.pop("posted_item", None),
                           deleted_item=session.pop("deleted_item", None),)


@app.post('/market')
@login_required
def market_post():
    check_modification(request, session["amazon_email"][:-10])

    if session.get("deleted_item") or session.get("posted_item"):
        return redirect(url_for('market_page'))

    products_db_filtered = products_db
    if category := request.form.get("category"):
        session["category"] = category

    if (search_item := request.form.get("search_item")) is not None:
        session["searched"] = search_item

    if (category := session.get("category")) and category != "all":
        products_db_filtered = products_db.loc[products_db["category"] == category]

    if search_item := session.get("searched", default=""):
        products_db_filtered = products_db_filtered.loc[products_db_filtered["item_name"].str.contains(search_item, case=False)]

    return render_template("Market.html",
                           users_db=users_db,
                           products_db=products_db_filtered,
                           amazon_email=session["amazon_email"],
                           search_item=search_item,)


@app.get('/market/<amazon_user>')
@login_required
def user_products(amazon_user):
    if amazon_user in products_db.index:
        products_db_filtered = products_db.loc[[amazon_user]]
    else:
        products_db_filtered = pd.DataFrame()

    return render_template("UserProducts.html",
                           amazon_user=amazon_user,
                           amazon_email=session["amazon_email"],
                           products_db=products_db_filtered,
                           users_db=users_db,
                           posted_item=session.pop("posted_item", None),
                           deleted_item=session.pop("deleted_item", None),)


# Only able to issue a "POST" request below if "amazon_user" == "amazon_email[:-10]"
@app.post('/market/<amazon_user>')
@login_required
def modify_product(amazon_user):
    check_modification(request, amazon_user)
    return redirect(url_for("user_products", amazon_user=amazon_user))


@app.get('/logout')
def logout():
    session.clear()
    return redirect(url_for("home_page"))


app.run(debug=True, host='0.0.0.0', port=3000)
