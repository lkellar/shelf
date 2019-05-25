from flask import Flask, g, request, jsonify, render_template
from os import path
from pathlib import Path
import sqlite3

from shelf import db

app = Flask(__name__, static_url_path='/static', static_folder='../static/',
            template_folder='../templates')
app.jinja_options = {'lstrip_blocks': True, 'trim_blocks': True}

currentDir = path.dirname(path.realpath(__file__))

# Gets the path to a database file right outside the src directory
DATABASE_PATH = str(Path(path.join(currentDir, '../', 'shelf.sqlite3')).resolve())
# The path to the simple word list
# TODO ATTRIBUTE WIKTIONARY AS SOURCE
WORD_PATH = path.join(currentDir, '../', 'words.json')

DB_MANAGER = None

@app.before_first_request
def startup():
    global DB_MANAGER
    # creates a DBManager instance
    DB_MANAGER = db.DBManager(DATABASE_PATH, WORD_PATH)


@app.route('/insert', methods=['GET','POST'])
def insert():
    # if a GET request, just send back the insert page
    if request.method == 'GET':
        return render_template('insert.html')

    # Takes data from POST request, and sends it to the database
    form = request.form

    #db cursor
    c = get_db().cursor()

    # generates a unique ID from a word list
    id = DB_MANAGER.generateID(c)

    # if the text snippet is public or not
    private = True if form['private'] == 'true' or form['private'] == 'on' else False

    # How many days the note will remain before expiration
    ttl_days = int(form['ttl_days']) if 'ttlDays' in form else 1

    # Max Page Visits before expiration
    max_visits = int(form['max_visits']) if 'max_visits' in form else 3

    DB_MANAGER.insert(id, form['note'], private, ttl_days, max_visits, c)

    # Returns confirmation page with details on how to retrieve note
    return render_template('confirmation.html', secret_code=id)


# TODO add api for fetch
@app.route('/fetch/<note_id>', methods=['GET'])
def fetch(note_id):
    # grabs a cursors for db
    c = get_db().cursor()

    # Fetches first (and only) article in database with provided id
    row = DB_MANAGER.fetchOne(note_id, c)

    # if the row exists, return the stored data
    if row:
        DB_MANAGER.updateVisits((row['visits'] + 1), note_id, c)
        if row['visits'] + 1 >= row['max_visits']:
            db.removeNote(note_id, DATABASE_PATH)
        return render_template('fetch.html', note=row)
    else:
        # if not, return a cool data not found message
        # TODO make this a webpage, not json
        return jsonify({'data': 'Entry Not Found'})



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