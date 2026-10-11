from flask import Blueprint, request, jsonify
from services.result_service import ResultService

result_bp = Blueprint("result", __name__)

service = ResultService()


@result_bp.route("/results", methods=["GET"])
def get_results():
    results = service.get_results()
    return jsonify(results)


@result_bp.route("/results/<int:result_id>", methods=["GET"])
def get_result(result_id):
    result = service.get_result(result_id)
    if result:
        return jsonify(result)
    return jsonify({"message": "Result not found"}), 404


@result_bp.route("/results", methods=["POST"])
def create_result():
    data = request.get_json()
    result = service.create_result(data)
    return jsonify(result), 201


@result_bp.route("/results/<int:result_id>", methods=["PUT"])
def update_result(result_id):
    data = request.get_json()
    updated_result = service.update_result(result_id, data)

    if updated_result:
        return jsonify(updated_result)

    return jsonify({"message": "Result not found"}), 404


@result_bp.route("/results/<int:result_id>", methods=["DELETE"])
def delete_result(result_id):
    service.remove_result(result_id)
    return jsonify({"message": "Result deleted successfully"})