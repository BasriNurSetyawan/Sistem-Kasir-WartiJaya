import hmac

from flask import current_app, jsonify, request

from app.routes import api_bp


@api_bp.before_request
def require_api_token():
    authorization = request.headers.get('Authorization', '')
    scheme, separator, supplied = authorization.partition(' ')
    expected = current_app.config['API_TOKEN']
    if (not separator or scheme.lower() != 'bearer' or not supplied
            or not hmac.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8'))):
        response = jsonify({'error': 'Token akses tidak valid atau tidak disertakan.'})
        response.status_code = 401
        response.headers['WWW-Authenticate'] = 'Bearer'
        return response
    return None
