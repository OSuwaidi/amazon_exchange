# بِسْمِ ٱللَّٰهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ وبه نستعين

from flask import Flask
from flask_mysqldb import MySQL
import app_secrets

app = Flask(__name__, static_url_path='/static')

app.config['MYSQL_HOST'] = app_secrets.mysql_host
app.config['MYSQL_USER'] = app_secrets.mysql_user
app.config['MYSQL_PASSWORD'] = app_secrets.mysql_pass
app.config['MYSQL_DB'] = app_secrets.mysql_db

mysql = MySQL(app)

user_details = {
        "email": ("osuwaidi@amazon.ae", "sadau@amazon.ae"),
        "password": ("admin",)*2,
        "first_name": ("Omar", "Sadaf"),
        "last_name": ("AlSuwaidi", "Usmani"),
}

prod_path = "/static/images/"
product_details = (
            {
                "owner": "osuwaidi",
                "item_name": "Zebra Printer",
                "item_desc": "Used to print different kind of labels for different sizes.",
                "price_per_unit": 750,
                "quantity": 2,
                "is_IT": True,
                "category": "OPT1",
                "img": prod_path+"printer.jpg",
                "date": "2022-06-25",
            },
            {
                "owner": "sadau",
                "item_name": "Honeywell Scanner",
                "item_desc": "A handheld Honeywell XP 1470g scanner in good condition.",
                "price_per_unit": 114.99,
                "quantity": 15,
                "is_IT": True,
                "category": "OPT1",
                "img": prod_path + "scanner.jpg",
                "date": "2021-01-16",
            },
            {
                "owner": "osuwaidi",
                "item_name": "Yellow Totes",
                "item_desc": "Two dozen of yellow plastic totes hanging around.",
                "price_per_unit": 10,
                "quantity": 139,
                "is_IT": False,
                "category": "OPT2",
                "img": prod_path + "totes.jpg",
                "date": "2023-01-07",
            },
)

with app.app_context():
    mysql.connection.autocommit(True)
    cursor = mysql.connection.cursor()
    cursor.execute("delete from products")
    query = f"insert into products values ({'%s, '*(len(product_details[0])-1)}%s)"
    values = [tuple(product.values()) for product in product_details]
    cursor.executemany(query, values)

    cursor.execute("delete from users")
    query = f"insert into users values ({'%s, '*(len(user_details)-1)}%s)"
    values = tuple(zip(*user_details.values()))
    cursor.executemany(query, values)
    cursor.close()
