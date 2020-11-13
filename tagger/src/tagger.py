from sanic import Sanic
from sanic.response import json
from sanic.exceptions import NotFound, MethodNotSupported

import traceback

import database
from TMVException import TMVException

app = Sanic('tmv-tagger')

def error(error_id, error_msg):
  return json({
    'error_id': error_id,
    'error_msg': error_msg
  })

# Expected format:
#
# [{
#   'name': STRING,
#   'required': BOOLEAN,
#   'type': STRING,
#    ?'empty': BOOLEAN
# }, ...]
def verify_input(request, expected):
  names = [e['name'] for e in expected]

  for name in request:
    if name not in names:
      raise TMVException(TMVException.ID_FAULTY_INPUT, 'Given parameter \'{}\' not expected'.format(name))

  for e in expected:
    if not e['name'] in request and e['required']:
      raise TMVException(TMVException.ID_FAULTY_INPUT, 'Required parameter \'{}\' not found in request body'.format(e['name']))
    elif not e['name'] in request:
      continue # Not in request and is optional, no need to check the rest

    param = request[e['name']]
    if e['type'] == 'str':
      if not isinstance(param, str):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string as expected'.format(e['name']))
    elif e['type'] == 'str[]':
      if not isinstance(param, list):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string array as expected'.format(e['name']))
      elif len(param) < 1 and not e['empty']:
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot be empty'.format(e['name']))
      else:
        for v in param:
          if not isinstance(v, str):
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string array as expected'.format(e['name']))
    elif e['type'] == 'val[]':
      if not isinstance(param, list):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not an array as expected'.format(e['name']))
      elif len(param) < 1 and not e['empty']:
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot be empty'.format(e['name']))
      else:
        for v in param:
          if not isinstance(v, dict):
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not an array of objects as expected'.format(e['name']))
          elif 'name' not in v or 'value' not in v:
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not an array of objects formatted as expected'.format(e['name']))
          elif not isinstance(v['name'], str) or not isinstance(v['value'], int):
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not an array of objects formatted as expected'.format(e['name']))
    elif e['type'] == 'qtag[]':
      if not isinstance(param, list):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not an array as expected'.format(e['name']))
      elif len(param) < 1 and not e['empty']:
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot be empty'.format(e['name']))
      else:
        for v in param:
          if not v in ['value', 'multi']:
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' can only contain \'value\', or \'multi\''.format(e['name']))


# Expected request format:
#
# {
#   'query': STRING[]
# }
#
# Expected response:
#
# {
#   ?'response': {
#     ?'value': [{'name': STRING, 'value': INTEGER}, ...]
#     ?'multi': STRING[]
#   },
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/search', methods=['POST'])
async def search(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'query',
      'required': True,
      'type': 'str[]',
      'empty': False
    }])

    result = database.search(request_body['query'])
    return json({'response': result})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    print(traceback.print_exception(type(e), e, e.__traceback__))
    return error(-1, 'Unknown error occured. Error type: \'{}\''.format(type(e).__name__))

# Expected request format:
#
# {
#   ?'value': STRING,
#   ?'value': STRING[],
#   ?'tags': [
#     ?'value',
#     ?'multi'
#   ]
# }
#
# Expected response:
#
# {
#   ?'response': {
#     ?'value': [{'name': STRING, 'value': INTEGER}, ...]
#     ?'multi': STRING[]
#   },
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/get', methods=['POST'])
async def get(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'value',
      'required': True,
      'type': 'str'
    }, {
      'name': 'tags',
      'required': False,
      'type': 'qtag[]',
      'empty': False
    }])

    tags = request_body['tags'] if 'tags' in request_body else None
    value = True if tags is None or 'value' in tags else False
    multi = True if tags is None or 'multi' in tags else False

    tagged = request_body['value'] if isinstance(request_body['value'], list) else [request_body['value']]
    result = database.get(tagged, value, multi)
    return json({'response': result})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    print(traceback.print_exception(type(e), e, e.__traceback__))
    return error(-1, 'Unknown error occured. Error type: \'{}\''.format(type(e).__name__))

# Expected request format:
#
# {
#   'value': STRING,
#   ?'multi_tags': STRING[],
#   ?'value_tags': [{'name': STRING, 'value': NUMBER}, ...],
# }
#
# Expected response:
#
# {
#   ?'success': BOOLEAN,
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/tag', methods=['POST'])
async def tag(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'value',
      'required': True,
      'type': 'str',
    }, {
      'name': 'multi_tags',
      'required': False,
      'type': 'str[]',
      'empty': False
    }, {
      'name': 'value_tags',
      'required': False,
      'type': 'val[]',
      'empty': False
    }])

    value_tags = request_body['value_tags'] if 'value_tags' in request_body else []
    multi_tags = request_body['multi_tags'] if 'multi_tags' in request_body else []

    database.tag(request_body['value'], value_tags, multi_tags)
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    print(traceback.print_exception(type(e), e, e.__traceback__))
    return error(-1, 'Unknown error occured. Error type: \'{}\''.format(type(e).__name__))

# Expected request format:
#
# {
#   'value': STRING,
#   ?'multi_tags': STRING[],
#   ?'value_tags': [{'name': STRING, 'value': NUMBER}, ...],
# }
#
# Expected response:
#
# {
#   ?'success': BOOLEAN,
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/untag', methods=['POST'])
async def untag(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'value',
      'required': True,
      'type': 'str',
    }, {
      'name': 'multi_tags',
      'required': False,
      'type': 'str[]',
      'empty': False
    }, {
      'name': 'value_tags',
      'required': False,
      'type': 'val[]',
      'empty': False
    }])

    value_tags = request_body['value_tags'] if 'value_tags' in request_body else []
    multi_tags = request_body['multi_tags'] if 'multi_tags' in request_body else []

    database.untag(request_body['value'], value_tags, multi_tags)
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    print(traceback.print_exception(type(e), e, e.__traceback__))
    return error(-1, 'Unknown error occured. Error type: \'{}\''.format(type(e).__name__))

# Exception handlers
@app.exception(NotFound)
async def not_found_exception(request, exception):
  return json({
    'error_id': TMVException.ID_404,
    'error_msg': 'Endpoint not found'
  })

@app.exception(MethodNotSupported)
async def not_found_exception(request, exception):
  return json({
    'error_id': TMVException.ID_405,
    'error_msg': 'Method \'{}\' is not supported. The TMV tagger only supports POST requests.'.format(request.method)
  })

if __name__ == '__main__':
  database.create_tables()
  app.run(host='0.0.0.0', port=8000)
