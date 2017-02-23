from flask import Flask
from flask import redirect
from flask import make_response
from flask_restful import Resource, Api, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import or_
from flask_restful import reqparse
from flask import send_from_directory, send_file
from re import findall
import hashlib
import urllib

app = Flask(__name__)
app.config['BASE_PATH'] = '/home/twintz/Musique/'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////music/library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
        parser.add_argument('filter[path]')
        args = parser.parse_args()
        filter_dict = dict()
        search = [getattr(self.Object, x).asc()
                  for x in self.Object.defaultSort]
        query = self.Object.query.order_by(*search)
        for name in self.columns:
            if args['filter[' + name + ']']:
                filter_dict[name] = args['filter[' + name + ']']
        query = query.filter_by(**filter_dict)
        if args['filter[path]']:
            prefix = args['filter[path]']
            prefix = app.config['BASE_PATH'] + prefix 
            query = self.Object.query.filter(self.Object.path.like(prefix + '%'))
            query = query.order_by(*search)
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
            print(items)
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
        parser.add_argument('filter[prefix]')
        parser.add_argument('filter[search]')
        args = parser.parse_args()
        path = ''
        search = [getattr(Items, x).asc()
                  for x in Items.defaultSort]
        if args['filter[prefix]']:
            path = args['filter[prefix]']
            if not path[-1] == '/':
                path = path + '/'
        prefix = app.config['BASE_PATH'] + path 
        query = Items.query.filter(Items.path.like(prefix + '%'))
        query = query.order_by(*search)
        if args['filter[search]']:
            selection = [getattr(Items, col).ilike(
                '%' + args['filter[search]'] + '%')
                           for col in Items.searchFields]
            query = query.filter(or_(*selection))
        items = query.all()
        def aux_subfolder(item):
            if len(item.path.decode('utf-8')[len(prefix):].split('/')) > 1:
                return (True, item.path.decode('utf-8')[len(prefix):].split('/')[0])
            else:
                return (False, item.path.decode('utf-8')[len(prefix):].split('/')[0])

        subfolders = {aux_subfolder(item)[1] for item in items if aux_subfolder(item)[0] }
        subfolders = list(subfolders)
        subfolders.sort()
        files = [aux_subfolder(item)[1] for item in items if not aux_subfolder(item)[0]]
        ids_files = [item.id for item in items if not aux_subfolder(item)[0]]
        ids = [int(hashlib.sha256(x.encode('utf-8')).hexdigest(), 16) for x in subfolders]
        return { 'data' : [ { 'attributes' : { 'name' : subfolders[i], 'folder' : True}, "id" : ids[i], "type" : "folder"} for i in range(len(subfolders))] +
                [ { 'attributes' : { 'name' : files[i], 'folder' : False}, "id" : ids_files[i], "type" : "folder"} for i in range(len(files))]}

api.add_resource(ItemsAPI, '/api/items', '/api/items/')
api.add_resource(ItemAPI, '/api/items/<request_id>')
api.add_resource(FoldersAPI, '/api/folders', '/api/folders/')
api.add_resource(AlbumsAPI, '/api/albums', '/api/albums/')
api.add_resource(AlbumAPI, '/api/albums/<request_id>')

# Files

mimetypes = {'MP3': 'audio/mpeg',
             'FLAC': 'audio/flac',
             'AAC': 'audio/x-aac'}


@app.route('/file/<item_id>')
def file(item_id):
    item_id = item_id.split('.')[0]
    item = Items.query.filter_by(id=item_id).first()
    item = Items.query.filter_by(id=item_id).first()
    path = item.path.decode('utf-8')
    server_path = path.replace(app.config['BASE_PATH'], '/music/')
    server_path = urllib.parse.quote(server_path)
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
