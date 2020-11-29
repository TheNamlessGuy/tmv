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

def unknown_error(exception):
  print(traceback.print_exception(type(exception), exception, exception.__traceback__))
  return error(-1, 'Unknown error occured. Error type: \'{}\''.format(type(exception).__name__))

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
    elif e['type'] == 'bool':
      if not isinstance(param, bool):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a boolean as expected'.format(e['name']))
    elif e['type'] == 'str[]':
      if not isinstance(param, list):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string array as expected'.format(e['name']))
      elif len(param) < 1 and not e['empty']:
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot be empty'.format(e['name']))
      else:
        for v in param:
          if not isinstance(v, str):
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string array as expected'.format(e['name']))
    elif e['type'] == 'str:str[]':
      if not isinstance(param, dict):
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a STRING: STRING[] dict as expectd'.format(e['name']))
      if len(param) < 1 and not e['empty']:
        raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot be empty'.format(e['name']))
      for k in param:
        if not isinstance(k, str):
          raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a STRING: STRING[] dict as expectd'.format(e['name']))
        v = param[k]
        if not isinstance(v, list):
          raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a STRING: STRING[] dict as expectd'.format(e['name']))
        if len(v) < 1 and not e['empty']:
          raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot have empty value lists'.format(e['name']))
        for s in v:
          if not isinstance(s, str):
            raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a STRING: STRING[] dict as expectd'.format(e['name']))
    elif e['type'] == 'str,str[]':
      if not isinstance(param, str):
        if not isinstance(param, list):
          raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string or string array as expected'.format(e['name']))
        elif len(param) < 1 and not e['empty']:
          raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' cannot be empty'.format(e['name']))
        else:
          for v in param:
            if not isinstance(v, str):
              raise TMVException(TMVException.ID_FAULTY_INPUT, 'Parameter \'{}\' not a string or string array as expected'.format(e['name']))
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
    return unknown_error(e)

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
#     <value>: {
#       ?'value': [{'name': STRING, 'value': INTEGER}, ...]
#       ?'multi': STRING[]
#     }, ...
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
      'type': 'str,str[]',
      'empty': False
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
    return unknown_error(e)

# Expected request format:
#
# {
#   'tags': [?'multi', ?'value']
# }
#
# Expected response
#
# {
#   ?'response': {
#     'multi_tags': STRING[],
#     'value_tags': [{'name': STRING, 'value': INTEGER}, ...]
#   },
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/get-tags', methods=['POST'])
async def get_tags(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'tags',
      'required': True,
      'type': 'qtag[]',
      'empty': False
    }])

    multi = 'multi' in request_body['tags']
    value = 'value' in request_body['tags']
    retval = database.get_tags(multi, value)
    return json({'response': retval})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

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
    return unknown_error(e)

# Expected request format:
#
# {
#   'value': STRING,
#   ?'multi_tags': STRING[],
#   ?'value_tags': [{'name': STRING, 'value': NUMBER}, ...],
#   ?'all': boolean
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
    }, {
      'name': 'all',
      'required': False,
      'type': 'bool'
    }])

    value_tags = request_body['value_tags'] if 'value_tags' in request_body else []
    multi_tags = request_body['multi_tags'] if 'multi_tags' in request_body else []
    all        = request_body['all'       ] if 'all'        in request_body else False

    if all:
      database.untag_all(request_body['value'])
    else:
      database.untag(request_body['value'], value_tags, multi_tags)
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

# Expected request format:
#
# {
#   ?'multi_tags': STRING[],
#   ?'value_tags': [{'name': string, 'value': INTEGER}, ...]
# }
#
# Expected response:
#
# {
#   ?'success': BOOLEAN,
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/delete-tags', methods=['POST'])
async def delete_tags(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'multi_tags',
      'required': False,
      'type': 'str[]',
      'empty': False,
    }, {
      'name': 'value_tags',
      'required': False,
      'type': 'val[]',
      'empty': False,
    }])

    multi = request_body['multi_tags'] if 'multi_tags' in request_body else []
    value = request_body['value_tags'] if 'value_tags' in request_body else []

    database.delete_tags(multi, value)
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

# Expected request format:
#
# {
#   ?'values': [{'old': STRING, 'new': STRING}, ...]
#   ?'value_tags': [{'old': {'name': STRING, 'value': INTEGER}, 'new': {'name': STRING, 'value': INTEGER}}, ...]
#   ?'multi_tags': [{'old': STRING, 'new': STRING}, ...]
# }
#
# Expected response:
#
# {
#   ?'success': BOOLEAN,
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/rename', methods=['POST'])
async def rename(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'values',
      'required': False,
      'type': 'oldnew[]',
      'empty': False
    }, {
      'name': 'multi_tags',
      'required': False,
      'type': 'oldnew[]',
      'empty': False
    }, {
      'name': 'value_tags',
      'required': False,
      'type': 'oldnew-val[]',
      'empty': False
    }])

    values    = request_body['values'    ] if 'values'     in request_body else []
    multitags = request_body['multi_tags'] if 'multi_tags' in request_body else []
    valuetags = request_body['value_tags'] if 'value_tags' in request_body else []

    if len(values) < 1 and len(multitags) < 1 and len(valuetags) < 1:
      raise TMVException(TMVException.ID_FAULTY_INPUT, 'At least one of the input fields \'values\', \'multi_tags\', \'value_tags\' has to not be empty')

    database.rename(values, multitags, valuetags)
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

# Expected request format
#
# {
#   'multi_tags': {
#     <multitag>: STRING[]
#   },
# }
#
# Expected response:
#
# {
#   ?'success': BOOLEAN,
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/tag-tags', methods=['POST'])
async def tag_tags(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'multi_tags',
      'required': True,
      'type': 'str:str[]',
      'empty': False
    }])

    database.tag_tags(request_body['multi_tags'])
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

# Expected request format
#
# {
#   'multi_tags': STRING[]
# }
#
# Expected response:
#
# {
#   ?'response': {
#     'multi_tags': {
#       <tag>: STRING[]
#     }
#   }
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/get-related-tags', methods=['POST'])
async def get_related_tags(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')
  try:
    verify_input(request_body, [{
      'name': 'multi_tags',
      'required': True,
      'type': 'str[]',
      'empty': False
    }])

    retval = database.get_implied_tags(request_body['multi_tags'])
    return json({'response': retval})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

# Expected request format
#
# {
#   'multi_tags': {
#     ?<multitag>: STRING[]
#     ?<multitag>: 'all'
#   },
# }
#
# Expected response:
#
# {
#   ?'success': BOOLEAN,
#   ?'error_id': INTEGER,
#   ?'error_msg': STRING,
# }
@app.route('/untag-tags', methods=['POST'])
async def untag_tags(request):
  try:
    request_body = request.json
  except Exception as e:
    return error(TMVException.ID_PARSE_JSON, 'Couldn\'t parse request body as JSON')

  try:
    verify_input(request_body, [{
      'name': 'multi_tags',
      'required': True,
      'type': 'str:str[]',
      'empty': False
    }])

    database.untag_tags(request_body['multi_tags'])
    return json({'success': True})
  except TMVException as e:
    return error(e.error_id, e.error_msg)
  except Exception as e:
    return unknown_error(e)

# Exception handlers
@app.exception(NotFound)
async def not_found_exception(request, exception):
  return error(TMVException.ID_404, 'Endpoint not found')

@app.exception(MethodNotSupported)
async def not_found_exception(request, exception):
  return error(TMVException.ID_405, 'Method \'{}\' is not supported. The TMV tagger only supports POST requests.'.format(request.method))

if __name__ == '__main__':
  database.create_tables()
  app.run(host='0.0.0.0', port=8000)

