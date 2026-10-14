from flask import Flask, jsonify, request
import logging, os, hmac
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from data_sources.base_provider import ProviderError
from database.migrations import migrate
from api.intelligence_routes import intelligence_bp
from config import DEBUG, HOST, PORT
from api.driver_routes import driver_bp
from api.constructor_routes import constructor_bp
from api.circuit_routes import circuit_bp
from api.race_routes import race_bp
from api.result_routes import result_bp
from api.import_routes import import_bp
from api.standings_routes import standings_bp
from api.prediction_routes import prediction_bp
from api.dashboard_routes import dashboard_bp
from api.regulation_routes import regulation_bp
from api.scenario_routes import scenario_bp
from api.history_routes import history_bp
from api.export_routes import export_bp
from api.odds_routes import odds_bp
from api.news_routes import news_bp
from api.weekend_routes import weekend_bp
from api.race_control_routes import race_control_bp
from api.session_refresh_routes import session_refresh_bp


def create_app():
    migrate()
    app = Flask(__name__)

    @app.before_request
    def protect_admin():
        admin_path = request.path.startswith(('/data/', '/model/retrain', '/odds/refresh', '/explanations/', '/news/', '/weekend/', '/race-control/'))
        if request.method == 'POST' and admin_path:
            if (request.path == '/race-control/sessions/refresh' or request.path.endswith('/stop')) and request.headers.get('Origin') not in (None, os.getenv('FRONTEND_ORIGIN', 'http://127.0.0.1:8090'), 'http://localhost:8090'):
                return jsonify(error={'code':'CROSS_ORIGIN_ADMIN','message':'Cross-origin refresh is not permitted'}),403
            token = os.getenv('ADMIN_TOKEN', '')
            if token and not hmac.compare_digest(request.headers.get('Authorization',''), 'Bearer ' + token):
                return jsonify(error={'code':'UNAUTHORIZED','message':'Admin authorization required','details':{}},message='Admin authorization required'),403
            if not token and request.remote_addr not in ('127.0.0.1','::1',None):
                return jsonify(error={'code':'LOCAL_ONLY','message':'Admin operations are local only','details':{}}),403

    @app.errorhandler(Exception)
    def handle_error(exc):
        if isinstance(exc,HTTPException): status,code,message=exc.code,exc.name.upper().replace(' ','_'),exc.description
        elif isinstance(exc,IntegrityError):status,code,message=409,'DATA_CONFLICT','A unique key or linked record prevents this change.'
        elif isinstance(exc,(ValueError,TypeError,KeyError)):status,code,message=400,getattr(exc,'code','INVALID_INPUT'),str(exc)
        elif isinstance(exc,PermissionError):status,code,message=403,'ACCESS_NOT_PERMITTED',str(exc)
        elif isinstance(exc,ProviderError):status,code,message=502,'PROVIDER_UNAVAILABLE',str(exc)
        else:
            status,code,message=500,'INTERNAL_ERROR','The operation could not be completed. Check the server log.'
        if status>=500:app.logger.exception('Request failed')
        return jsonify(error={'code':code,'message':message,'details':{}},message=message),status


    # Normalize legacy error responses while retaining their message field.
    @app.after_request
    def normalize_error(response):
        if response.status_code >= 400 and response.is_json:
            data=response.get_json() or {}
            if not isinstance(data.get('error'),dict):
                data['error']={'code':{400:'INVALID_INPUT',404:'NOT_FOUND',409:'DATA_CONFLICT'}.get(response.status_code,'REQUEST_FAILED'),'message':data.get('message','The request could not be completed.'),'details':{}}
                response.set_data(app.json.dumps(data))
        return response

    # Browser-origin access is limited to the configured frontend.
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        allowed = os.getenv('FRONTEND_ORIGIN', 'http://127.0.0.1:8090')
        if origin == allowed:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin' 
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    app.register_blueprint(driver_bp)
    app.register_blueprint(constructor_bp)
    app.register_blueprint(circuit_bp)
    app.register_blueprint(race_bp)
    app.register_blueprint(result_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(standings_bp)
    app.register_blueprint(prediction_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(regulation_bp)
    app.register_blueprint(scenario_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(odds_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(weekend_bp)
    app.register_blueprint(race_control_bp)
    app.register_blueprint(session_refresh_bp)

    app.register_blueprint(intelligence_bp)

    return app


app = create_app()

if __name__ == "__main__":
    from services.news_service import NewsScheduler
    NewsScheduler.start()
    app.run(debug=DEBUG, host=HOST, port=PORT, use_reloader=False)
