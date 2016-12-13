from flask import Flask
from flask_restful import Resource, Api
from flask_sqlalchemy import SQLAlchemy
from flask_restful import reqparse

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False;
api = Api(app)
db = SQLAlchemy(app)

import flask
from flask import send_from_directory, send_file

# API
class Items(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String())
    artist = db.Column(db.String())
    track = db.Column(db.Integer)
    album_id = db.Column(db.Integer)
    album = db.Column(db.String())
    disc = db.Column(db.Integer())
    length = db.Column(db.Float())


class Albums(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    album = db.Column(db.String())
    albumartist = db.Column(db.String())


def format_item(item):
    return { 
            'type' : 'items',
            'id' : str(item.id),
                'attributes' : {
                    'title' : item.title,
                    'artist' : item.artist,
                    'track' : item.track,
                    'album_id' : item.album_id,
                    'album' : item.album,
                    'disc' : item.disc,
                    'length' : item.length
                }
            } 


def format_album(album):
    return {
                'type' : 'albums',
                'id' : str(album.id),
                'attributes' : {
                    'album' : album.album,
                    'albumartist' : album.albumartist
                }
            }

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
        d = { column : getattr(item, column) for column in self.columns }
        return {
                'type' : self.objectStr,
                'id' : str(item.id),
                'attributes' : d
                }
    def get(self):
        parser = reqparse.RequestParser()
        for name in self.columns:
            parser.add_argument('filter[' + name +']')
        args = parser.parse_args()
        filter_dict = dict()
        for name in self.columns:
            if args['filter[' + name +']']:
                filter_dict[name] = args['filter[' + name +']']
        items = self.Object.query.filter_by(**filter_dict).all()
        return {'data' : [self.format(item) for item in items]}
    
class ItemsAPI(genericAPI):
    Object = Items
    objectStr="items"

class AlbumsAPI(genericAPI):
    Object = Albums
    objectStr="albums"

class Hello(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('filter')
        args = parser.parse_args()
        return {'params' : args['filter']['test']}


api.add_resource(ItemsAPI, '/items/')
api.add_resource(AlbumsAPI, '/albums/')
api.add_resource(Hello, '/hello/')

# UI.

@app.route('/')
def home():
    return send_file('static/index.html')
@app.route('/queue/')
def queue():
    return send_file('static/index.html')
@app.route('/tracks/')
def tracks():
    return send_file('static/index.html')

@app.route('/<path:filename>')
def send_resource(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)
