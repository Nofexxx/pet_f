from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import xml.sax


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#определение моделей базы данных
class File(db.Model):
    __tablename__ = 'Files'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)


class Tag(db.Model):
    __tablename__ = 'Tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('Files.id'), nullable=False)


class Attribute(db.Model):
    __tablename__ = 'Attributes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    value = db.Column(db.String, nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('Tags.id'), nullable=False)

#создание базы данных
with app.app_context():
    db.create_all()


class XMLHandler(xml.sax.ContentHandler):
    def __init__(self, file_id):
        self.file_id = file_id
        self.tag_stack = []  #используем стек для вложенности

    def startElement(self, name, attrs):
        tag = Tag(name=name, file_id=self.file_id)
        db.session.add(tag)
        db.session.commit()

        self.tag_stack.append(tag.id) #сохраняем id текущего тега

        for attr_name, attr_value in attrs.items():
            attribute = Attribute(name=attr_name, value=attr_value, tag_id=tag.id)
            db.session.add(attribute)

        db.session.commit()

    def endElement(self, name):
        if self.tag_stack:
            self.tag_stack.pop() # удаляем последний элемент при выходе из тега



@app.route('/api/file/read', methods=['POST'])
def upload_file():
    #проверяем, есть ли файл в запросе
    if 'file' not in request.files:
        return jsonify({'succses': False, 'error': 'No file found'}), 400

    file = request.files['file']
    file_name = file.filename

    #проверяем, передано ли имя файла
    if file_name == '':
        return jsonify({'success': False, 'error': 'No file name'}), 400

    #проверка наличия в БД
    existing_file = File.query.filter_by(name=file_name).first()
    if existing_file:
        return jsonify({'success': False, 'error': 'File already exists'}), 400

    #сохранение фала в БД
    new_file = File(name=file_name)
    db.session.add(new_file)
    db.session.commit()

    #разбор XML
    parser = xml.sax.make_parser()
    parser.setContentHandler(XMLHandler(new_file.id))
    try:
        parser.parse(file)
        return jsonify({'success': True})
    except xml.sax.SAXException:
        return jsonify({'success': False, 'error': 'File could not be parsed'}), 400


@app.route('/api/tags/get-count', methods=['GET'])
def get_tag_count():
    file_name = request.args.get('file')
    tag_name = request.args.get('tag')

    if not (file_name and tag_name):
        return jsonify({'success': False, 'error': 'No file specified'}), 400

    file = File.query.filter_by(name=file_name).first()
    if not file:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    count = Tag.query.filter_by(name=tag_name, file_id=file.id).count()
    if not count:
        return jsonify({'success': False, 'error': 'Tag not found'}), 404

    return jsonify({'success': True, 'count': count})


@app.route('/api/tags/attributes/get', methods=['GET'])
def get_tag_attributes():
    file_name = request.args.get('file')
    tag_name = request.args.get('tag')

    if not (file_name and tag_name):
        return jsonify({'success': False, 'error': 'No file specified'}), 400

    file = File.query.filter_by(name=file_name).first()
    if not file:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    tags = Tag.query.filter_by(name=tag_name).all()
    if not tags:
        return jsonify({'success': False, 'error': 'Tag not found'}), 404

    unique_attributes = set()
    for tag in tags:
        attributes = Attribute.query.filter_by(tag_id=tag.id).all()
        for attribute in attributes:
            unique_attributes.add(attribute.name)

    return jsonify({'success': True, 'unique_attributes': list(unique_attributes)})