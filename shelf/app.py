from flask import Flask, g, request, jsonify, render_template, redirect, url_for, abort
from flask.json import JSONEncoder
from datetime import datetime
from os import path
from pathlib import Path
import sqlite3

from shelf.db import DBManager, remove_note


# Formats all dates in json in proper iso format
class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                # Convert to iso format timezone, and add the Z, to indicate
                # utc time
                return obj.isoformat() + 'Z'
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)


app = Flask(__name__, static_url_path='/static', static_folder='../static/',
            template_folder='../templates')
app.jinja_options = {'lstrip_blocks': True, 'trim_blocks': True}
app.json_encoder = CustomJSONEncoder

currentDir = path.dirname(path.realpath(__file__))

# Gets the path to a database file right outside the src directory
DATABASE_PATH = str(Path(path.join(currentDir, '../', 'shelf.sqlite3')).resolve())
# The path to the simple word list
WORD_PATH = path.join(currentDir, '../', 'words.json')

DB_MANAGER = None

MIN_TTL_DAYS = 1
MIN_MAX_VISITS = 1


@app.before_first_request
def startup():
    global DB_MANAGER
    # creates a DBManager instance
    DB_MANAGER = DBManager(DATABASE_PATH, WORD_PATH)


@app.route('/')
def index():
    # Just returning the homepage
    return render_template('index.html')


@app.route('/insert', methods=['GET', 'POST'])
def client_insert():
    # If a user tries to go to /insert with no params, just send them back
    # to the home page so they can insert their data
    if request.method == 'GET':
        return redirect(url_for('index'))

    # Takes data from POST request, and sends it to the database
    form = request.form

    # Send params to shared insert function for processing,
    # then receive note metadata
    note_data = insert(form)

    # Returns confirmation page with details on how to retrieve note
    return render_template('confirmation.html', note_id=note_data['id'],
                           expiry_date=note_data['expiry_date'],
                           max_visits=note_data['max_visits'],
                           min_max_visits=MIN_MAX_VISITS,
                           min_ttl_days=MIN_TTL_DAYS)


# TODO add api for fetch
@app.route('/fetch/<note_id>', methods=['GET'])
def client_fetch(note_id):
    note = fetch(note_id)

    # if the row exists, return the stored data
    if note:
        return render_template('fetch.html', note=note)
    else:
        # if not, return a cool data not found message
        return redirect(url_for('index', find='failed', _external=True,
                                _scheme='https'))


# API endpoints
@app.route('/api/insert', methods=['POST'])
def api_insert():
    # Basically a much simpler version of client_insert
    form = request.form

    try:
        note_data = insert(form)
    except ValueError:
        abort(400)

    return jsonify(note_data)


@app.route('/api/fetch/<note_id>', methods=['GET'])
def api_fetch(note_id):
    note = fetch(note_id)

    if note:
        return jsonify(dict(note))
    else:
        # If no note, return an empty dictionary,
        # this way, there's no custom error message, and if the empty response
        # is converted into boolean (like "if note:"), it'll be false
        return jsonify({})


# Shared Functions for use by multiple endpoints
def insert(form):
    # db cursor
    c = get_db().cursor()

    # generates a unique ID from a word list
    note_id = DB_MANAGER.generate_id(c)

    # if the text snippet is public or not
    private = True if form['private'] == 'true' or form['private'] == 'on'\
        else False

    # How many days the note will remain before expiration
    ttl_days = int(form['ttl_days']) if 'ttl_days' in form else 1

    # Max Page Visits before expiration
    max_visits = int(form['max_visits']) if 'max_visits' in form else 2

    # We can't have people putting in negative numbers, that would be bad
    if ttl_days < MIN_TTL_DAYS or max_visits < MIN_MAX_VISITS:
        raise ValueError()

    # Insert the note into the DB_Manager's insert function, which inserts
    # into db then, returns the expiry date and note id.
    note_data = DB_MANAGER.insert(note_id, form['note'], private, ttl_days, max_visits, c)

    return note_data


def fetch(note_id):
    # grabs a cursors for db
    c = get_db().cursor()

    # Fetches first (and only) article in database with provided id
    row = DB_MANAGER.fetch_one(note_id, c)

    if row:
        DB_MANAGER.update_visits((row['visits'] + 1), note_id, c)
        if row['visits'] + 1 >= row['max_visits']:
            remove_note(note_id, DATABASE_PATH)
        return row

    return False


def get_db():
    db = getattr(g, '_database', None)
    if not db:
        db = g._database = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g._database.row_factory = sqlite3.Row

    return db


@app.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()


if __name__ == '__main__':
    app.run()
    startup()
