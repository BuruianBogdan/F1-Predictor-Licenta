from flask import Blueprint, request, jsonify
from services.constructor_service import ConstructorService

constructor_bp = Blueprint("constructor", __name__)

service = ConstructorService()


@constructor_bp.route("/constructors", methods=["GET"])
def get_constructors():
    constructors = service.get_constructors()
    return jsonify(constructors)


@constructor_bp.route("/constructors/<int:constructor_id>", methods=["GET"])
def get_constructor(constructor_id):
    constructor = service.get_constructor(constructor_id)
    if constructor:
        return jsonify(constructor)
    return jsonify({"message": "Constructor not found"}), 404


@constructor_bp.route("/constructors", methods=["POST"])
def create_constructor():
    data = request.get_json()
    constructor = service.create_constructor(data)
    return jsonify(constructor), 201


@constructor_bp.route("/constructors/<int:constructor_id>", methods=["PUT"])
def update_constructor(constructor_id):
    data = request.get_json()
    updated_constructor = service.update_constructor(constructor_id, data)

    if updated_constructor:
        return jsonify(updated_constructor)

    return jsonify({"message": "Constructor not found"}), 404


@constructor_bp.route("/constructors/<int:constructor_id>", methods=["DELETE"])
def delete_constructor(constructor_id):
    service.remove_constructor(constructor_id)
    return jsonify({"message": "Constructor deleted successfully"})