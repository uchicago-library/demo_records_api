import logging

from flask import Blueprint, abort, Response
from flask_restful import Resource, Api, reqparse
from pymongo import MongoClient, ASCENDING


BLUEPRINT = Blueprint('idnest', __name__)


BLUEPRINT.config = {}


API = Api(BLUEPRINT)


log = logging.getLogger(__name__)


class MongoStorageBackend:
    def __init__(self, bp):
        client = MongoClient(bp.config["MONGO_HOST"],
                             bp.config.get("MONGO_PORT", 27017))
        self.db = client[bp.config["MONGO_DB"]]

    def mint_collection(self, id, name, note=""):
        self.db.collections.insert_one({'name': name, '_id': id, 'note': note, 'accs': []})
        return id

    def edit_collection_name(self, c_id, name):
        self.db.collections.update_one({'_id': c_id}, {'$set': {'name': name}})

    def edit_collection_note(self, c_id, note):
        self.db.collections.update_one({'_id': c_id}, {'$set': {'note': note}})

    def rm_collection(self, c_id):
        self.db.collections.delete_one({'_id': c_id})
        return c_id

    def ls_collections(self, cursor, limit):
        def peek(cursor, limit):
            if len([str(x['_id']) for x in
                    self.db.collections.find().sort('_id', ASCENDING).\
                    skip(cursor+limit).limit(1)]) > 0:
                    return str(cursor+limit)
            else:
                    return None
        cursor = int(cursor)
        return peek(cursor, limit), [(str(x['_id']), str(x['name']))
                                     for x in self.db.collections.find().sort(
                                         '_id', ASCENDING).skip(cursor).limit(limit)]

    def collection_exists(self, c_id):
        return bool(self.db.collections.find_one({'_id': c_id}))

    def get_collection(self, c_id):
        return self.db.collections.find_one({'_id': c_id})

    def associate_acc_with_collection(self, c_id, a_id):
        self.db.collections.update_one({'_id': c_id}, {'$push': {'accs': a_id}})

    def deassociate_acc_with_collection(self, c_id, a_id):
        self.db.collections.update_one({'_id': c_id}, {'$pull': {'accs': a_id}})

    def mint_accrec(self, a_id, note="", linked_acc=None, associated_external_ids=[], linked_cid=None):
        if linked_cid:
            if not self.collection_exists(linked_cid):
                abort(500)
            self.associate_acc_with_collection(linked_cid, a_id)
        self.db.accessions.insert_one({'_id': a_id, 'note': note, 'linked_acc': linked_acc,
                                       'associated_external_ids': associated_external_ids})
        return id

    def edit_accrec_note(self, a_id, note):
        self.db.accessions.update_one({'_id': a_id}, {'$set': {'note': note}})

    def edit_accrec_linked_acc(self, a_id, linked_acc):
        self.db.accessions.update_one({'_id': a_id}, {'$set': {'linked_acc': linked_acc}})

    def add_accrec_associated_external_id(self, a_id, ext_id):
        self.db.accessions.update_one({'_id': a_id}, {'$push': {'associated_external_ids': ext_id}})

    def ls_accessionrecs(self, c_id):
        if not self.collection_exists(c_id):
            raise ValueError
        return self.db.collections.find_one({'_id': c_id})['accs']

    def acc_exists(self, a_id):
        return bool(self.db.accessions.find_one({'_id': a_id}))

    def rm_accrec(self, a_id):
        self.db.accessions.delete_one({'_id': a_id})
        return a_id

    def get_accrec(self, a_id):
        return self.db.accessions.find_one({'_id': a_id})


def output_html(data, code, headers=None):
    # https://github.com/flask-restful/flask-restful/issues/124
    resp = Response(data, mimetype='text/html', headers=headers)
    resp.status_code = code
    return resp

pagination_args_parser = reqparse.RequestParser()
pagination_args_parser.add_argument(
    'cursor', type=str, default="0"
)
pagination_args_parser.add_argument(
    'limit', type=int, default=1000
)


def check_limit(limit):
    if limit > BLUEPRINT.config.get("MAX_LIMIT", 1000):
        log.warning(
            "Received request above MAX_LIMIT (or 1000 if undefined), capping.")
        limit = BLUEPRINT.config.get("MAX_LIMIT", 1000)
    return limit


class Root(Resource):
    def get(self):
        log.info("Received GET @ root endpoint")
        return {
            "collection_records": API.url_for(Collections),
            "accession_records": API.url_for(Accessions),
            "_self": {'_link': API.url_for(Root),
                      'identifier': None}
        }


class Collections(Resource):
    def get(self):
        log.info("Received GET @ collections endpoint")
        log.debug("Parsing args")
        parser = pagination_args_parser.copy()
        args = parser.parse_args()
        args['limit'] = check_limit(args['limit'])
        next_cursor, paginated_ids = \
            BLUEPRINT.config['storage'].ls_collections(cursor=args['cursor'], limit=args['limit'])
        return {
            "Collection_Records": [{"identifier": x[0],
                                    "name": x[1],
                                    "_link": API.url_for(Collection, collection_id=x)}
                                   for x in paginated_ids],
            "pagination": {
                "cursor": args['cursor'],
                "limit": args['limit'],
                "next_cursor": next_cursor
            },
            "_self": {"identifier": None, "_link": API.url_for(Collections)}
        }


class Collection(Resource):
    def put(self, collection_id):
        log.info("Received POST @ collection endpoint")
        if BLUEPRINT.config['storage'].collection_exists(collection_id):
            abort(500)
        log.debug("Parsing args")
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True)
        parser.add_argument('note', type=str)
        args = parser.parse_args()
        log.debug("Args parsed")
        return BLUEPRINT.config['storage'].mint_collection(collection_id, args['name'], args.get('note'))

    def get(self, collection_id):
        log.info("Received GET @ collection endpoint")
        if not BLUEPRINT.config['storage'].collection_exists(collection_id):
            abort(404)
        return BLUEPRINT.config['storage'].get_collection(collection_id)

    def delete(self, collection_id):
        log.info("Received DELETE @ collection endpoint")
        BLUEPRINT.config['storage'].rm_collection(collection_id)
        return {
            "Deleted": True,
            "_self": {"identifier": collection_id, "_link": API.url_for(Collection, collection_id=collection_id)}
        }


class CollectionEditName(Resource):
    def get(self, c_id):
        return BLUEPRINT.config['storage'].get_collection(c_id)['name']

    def put(self, c_id):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].edit_collection_name(c_id, args['name'])
        return c_id


class CollectionEditNote(Resource):
    def get(self, c_id):
        return BLUEPRINT.config['storage'].get_collection(c_id)['note']

    def put(self, c_id):
        parser = reqparse.RequestParser()
        parser.add_argument('note', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].edit_collection_note(c_id, args['note'])
        return c_id


class CollectionLinkedAccs(Resource):
    def get(self, c_id):
        return BLUEPRINT.config['storage'].get_collection(c_id)['accs']

    def post(self, c_id):
        parser = reqparse.RequestParser()
        parser.add_argument('accrec_id', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].associate_acc_with_collection(c_id, args['accrec_id'])
        return c_id

    def delete(self, c_id):
        parser = reqparse.RequestParser()
        parser.add_argument('accrec_id', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].deassociate_acc_with_collection(c_id, args['accrec_id'])
        return c_id


class Accessions(Resource):
    pass


class Accession(Resource):
    def put(self, acc_id):
        # TODO: Don't clobber things
        parser = reqparse.RequestParser()
        parser.add_argument('note', type=str)
        parser.add_argument('linked_acc', type=str)
        parser.add_argument('associated_cid', type=str)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].mint_accrec(
            acc_id, note=args.get('note', ""), linked_acc=args.get('linked_acc'),
            linked_cid=args.get('associated_cid')
        )

    def get(self, acc_id):
        return BLUEPRINT.config['storage'].get_accrec(acc_id)

    def delete(self, acc_id):
        pass


class AccessionEditNote(Resource):
    def get(self, a_id):
        return BLUEPRINT.config['storage'].get_accrec(a_id)['note']

    def put(self, a_id):
        parser = reqparse.RequestParser()
        parser.add_argument('note', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].edit_accrec_note(a_id, args['note'])
        return a_id


class AccessionLinkId(Resource):
    def get(self, a_id):
        return BLUEPRINT.config['storage'].get_accrec(a_id)['linked_acc']

    def put(self, a_id):
        parser = reqparse.RequestParser()
        parser.add_argument('linked_acc', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].edit_accrec_linked_acc(a_id, args['linked_acc'])
        return a_id


class AccessionExternalIds(Resource):
    def get(self, a_id):
        return BLUEPRINT.config['storage'].get_accrec(a_id)['associated_external_ids']

    def post(self, a_id):
        parser = reqparse.RequestParser()
        parser.add_argument('external_id', type=str, required=True)
        args = parser.parse_args()
        BLUEPRINT.config['storage'].add_accrec_associated_external_id(a_id, args['external_id'])
        return a_id


# Let the application context clobber any config options here
@BLUEPRINT.record
def handle_configs(setup_state):
    app = setup_state.app
    BLUEPRINT.config.update(app.config)

    if BLUEPRINT.config.get("DEFER_CONFIG"):
        return

    BLUEPRINT.config['storage'] = MongoStorageBackend(BLUEPRINT)

    if BLUEPRINT.config.get("VERBOSITY") is None:
        BLUEPRINT.config["VERBOSITY"] = "WARN"
    logging.basicConfig(level=BLUEPRINT.config["VERBOSITY"])


@BLUEPRINT.before_request
def before_request():
    # Check to be sure all our pre-request configuration has been done.
    if not isinstance(BLUEPRINT.config.get('storage'), MongoStorageBackend):
        raise RuntimeError()
        abort(500)


API.add_resource(Root, "/")
API.add_resource(Collections, "/collections")
API.add_resource(Accessions, "/accessions")
API.add_resource(Collection, "/collections/<string:collection_id>")
API.add_resource(CollectionEditName, "/collections/<string:c_id>/editName")
API.add_resource(CollectionEditNote, "/collections/<string:c_id>/editNote")
API.add_resource(CollectionLinkedAccs, "/collections/<string:c_id>/linkedAccs")
API.add_resource(Accession, "/accessions/<string:acc_id>")
API.add_resource(AccessionLinkId, "/accessions/<string:a_id>/linkedId")
API.add_resource(AccessionEditNote, "/accessions/<string:a_id>/editNote")
API.add_resource(AccessionExternalIds, "/accessions/<string:a_id>/externalIds")
