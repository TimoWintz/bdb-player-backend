from flask import Flask
from flask import redirect
from flask import make_response
from flask_restful import Resource, Api, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import or_
from flask_restful import reqparse
from flask import send_from_directory, send_file
from re import findall

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['BASE_PATH'] = '/home/twintz/Musique/'
api = Api(app)
db = SQLAlchemy(app)


# API
class Items(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    title = db.Column(db.String())
    artist = db.Column(db.String())
    albumartist = db.Column(db.String())
    track = db.Column(db.Integer)
    album_id = db.Column(db.Integer)
    album = db.Column(db.String())
    disc = db.Column(db.Integer())
    length = db.Column(db.Float())
    path = db.Column(db.String())
    format = db.Column(db.String())
    hidden = {"path"}
    searchFields = {"title", "artist", "album"}
    defaultSort = ["albumartist", "album", "disc", "track"]


class Albums(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    album = db.Column(db.String())
    year = db.Column(db.Integer())
    month = db.Column(db.Integer())
    albumartist = db.Column(db.String())
    hidden = {}
    searchFields = {"album", "albumartist"}
    defaultSort = ["albumartist", "year", "month"]


class genericAPI(Resource):

    @property
    def objectStr(self):
        raise NotImplementedError

    @property
    def Object(self):
        raise NotImplementedError

    @property
    def columns(self):
        return self.Object.__table__.columns.keys()

    def format(self, item):
        d = {column: getattr(item, column)
             for column in self.columns if column not in self.Object.hidden}
        return {
            'type': self.objectStr,
            'id': str(item.id),
            'attributes': d
        }

    def get(self):
        parser = reqparse.RequestParser()
        for name in self.columns:
            parser.add_argument('filter[' + name + ']')
        parser.add_argument('filter[search]')
        parser.add_argument('page[number]')
        parser.add_argument('page[size]')
        args = parser.parse_args()
        filter_dict = dict()
        search = [getattr(self.Object, x).asc()
                  for x in self.Object.defaultSort]
        query = self.Object.query.order_by(*search)
        for name in self.columns:
            if args['filter[' + name + ']']:
                filter_dict[name] = args['filter[' + name + ']']
        query = query.filter_by(**filter_dict)
        if args['filter[search]']:
            selection = [getattr(self.Object, col).ilike(
                '%' + args['filter[search]'] + '%')
                           for col in self.Object.searchFields]
            query = query.filter(or_(*selection))
        if args['page[number]'] and args['page[size]']:
            pagination = query.paginate(
                page=int(args['page[number]']),
                per_page=int(args['page[size]']))
            items = pagination.items
            return {'meta': {'total-pages': pagination.pages},
                    'data': [self.format(item) for item in items]}
        else:
            items = query.all()
            return {'data': [self.format(item) for item in items]}


class genericSingle(genericAPI):

    def get(self, request_id):
        try:
            item = self.Object.query.filter_by(id=request_id).first()
            return {'data': self.format(item)}
        except:
            abort(404, message=self.objectStr + " not found.")


class ItemsAPI(genericAPI):
    Object = Items
    objectStr = "item"


class ItemAPI(genericSingle):
    Object = Items
    objectStr = "item"


class AlbumsAPI(genericAPI):
    Object = Albums
    objectStr = "album"


class AlbumAPI(genericSingle):
    Object = Albums
    objectStr = "album"

class FoldersAPI(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('prefix')
        args = parser.parse_args()
        path = ''
        if args['prefix']:
            path = args['prefix']
            if not path[-1] == '/':
                path = path + '/'
        prefix = app.config['BASE_PATH'] + path 
        query = Items.query.filter(Items.path.like(prefix + '%'))
        subfolders = {item.path.decode('utf-8')[len(prefix):].split('/')[0] for item in query.all()}
        subfolders = list(subfolders)
        subfolders.sort()
        ids = range(len(subfolders))
        return { 'data' : [ { 'attributes' : { 'name' : subfolders[i] }, "id" : ids[i]} for i in range(len(subfolders))]}

api.add_resource(ItemsAPI, '/api/items', '/api/items/')
api.add_resource(ItemAPI, '/api/items/<request_id>')
api.add_resource(FoldersAPI, '/api/files', '/api/files/')
api.add_resource(AlbumsAPI, '/api/albums', '/api/albums/')
api.add_resource(AlbumAPI, '/api/albums/<request_id>')

# Files

mimetypes = {'MP3': 'audio/mpeg',
             'FLAC': 'audio/flac',
             'AAC': 'audio/x-aac'}


@app.route('/file/<item_id>')
def file(item_id):
    item = Items.query.filter_by(id=item_id).first()
    path = item.path.decode('utf-8')
    server_path = path.replace(app.config['BASE_PATH'], '/music/')
    return redirect(server_path)

# UI.


@app.route('/')
def home():
    return send_from_directory('static', 'index.html')


@app.route('/queue/')
def queue():
    return send_from_directory('static', 'index.html')


@app.route('/tracks/')
def tracks():
    return send_from_directory('static', 'index.html')


@app.route('/album/<path:path>')
def album(path):
    return send_from_directory('static', 'index.html')


@app.route('/<path:filename>')
def send_resource(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    app.run(debug=True)
