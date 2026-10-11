from flask import Blueprint, request, jsonify
from services.circuit_service import CircuitService

circuit_bp = Blueprint("circuit", __name__)

service = CircuitService()


@circuit_bp.route("/circuits", methods=["GET"])
def get_circuits():
    circuits = service.get_circuits()
    return jsonify(circuits)


@circuit_bp.route("/circuits/<int:circuit_id>", methods=["GET"])
def get_circuit(circuit_id):
    circuit = service.get_circuit(circuit_id)
    if circuit:
        return jsonify(circuit)
    return jsonify({"message": "Circuit not found"}), 404


@circuit_bp.route("/circuits", methods=["POST"])
def create_circuit():
    data = request.get_json()
    circuit = service.create_circuit(data)
    return jsonify(circuit), 201


@circuit_bp.route("/circuits/<int:circuit_id>", methods=["PUT"])
def update_circuit(circuit_id):
    data = request.get_json()
    updated_circuit = service.update_circuit(circuit_id, data)

    if updated_circuit:
        return jsonify(updated_circuit)

    return jsonify({"message": "Circuit not found"}), 404


@circuit_bp.route("/circuits/<int:circuit_id>", methods=["DELETE"])
def delete_circuit(circuit_id):
    service.remove_circuit(circuit_id)
    return jsonify({"message": "Circuit deleted successfully"})